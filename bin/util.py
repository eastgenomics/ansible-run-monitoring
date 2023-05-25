import collections
import datetime as dt
import dxpy as dx
import json
import os
import pickle
import requests

from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from dateutil.relativedelta import relativedelta

from .helper import get_logger

log = get_logger("util log")


def post_message_to_slack(
    channel: str,
    token: str,
    data,
    debug: bool,
    usage: tuple = (0, 0, 0),
    today: dt.datetime = None,
    jira_url: str = None,
    notification: bool = False,
    stale: bool = False,
) -> None:
    """
    Function to send Slack notification
    Inputs:
        channel: e.g. egg-alerts
        token: slack token
        data: str or dict
        debug: whether debug mode (channel: egg-test) or not
        usage: disk size usage (tuple)
        today: datetime
        jira_url: jira_slack_notify url
        notification: True if complicated msg
        stale: True when sending stale run
    """

    log.info(f"Sending POST request to channel: #{channel}")

    http = requests.Session()
    retries = Retry(total=5, backoff_factor=10, method_whitelist=["POST"])
    http.mount("https://", HTTPAdapter(max_retries=retries))

    if debug:
        channel = "egg-test"

    if notification:
        # complicated msg sending where
        # msg is a dict which need to be compiled
        # into multiple Slack msg (if too long)
        final_msg = []
        data_count = 0

        for run, body in data.items():
            seq = body["seq"]
            key = body["key"]
            status = body["status"]
            assay = body["assay"]
            size = body["size"]
            gtotal = round(usage[0] / 1024 / 1024 / 1024, 2)
            gused = round(usage[1] / 1024 / 1024 / 1024, 2)
            gpercent = round((usage[1] / usage[0]) * 100, 2)

            # format message depending on msg type
            if stale:
                # send about stale run
                created_date = body["created"]
                url = body["url"]

                created_dt = dt.datetime.strptime(created_date, "%Y-%m-%d")
                duration = today - created_dt

                if duration.days > 1 and key is None:
                    # if there's no jira ticket
                    # and runs have been more than 1 day
                    final_msg.append(
                        f"`/genetics/{seq}/{run}`\n"
                        "Run is missing associated Jira ticket"
                    )
                    final_msg.append(
                        f"><{url}|DNANexus Link>\n"
                        f">{duration.days // 7} weeks "
                        f"{duration.days % 7} days ago\n"
                    )
                    data_count += 1
                elif (
                    duration.days > 30
                    and status.upper() != "ALL SAMPLES RELEASED"
                ):
                    # if ticket is old
                    # and status still not released
                    final_msg.append(
                        f"`/genetics/{seq}/{run}`\n"
                        "Run still not released "
                        f"<{jira_url}{key}|{status}>"
                    )
                    final_msg.append(
                        f"><{url}|DNANexus Link>\n"
                        f">{duration.days // 7} weeks "
                        f"{duration.days % 7} days ago\n"
                    )
                    data_count += 1
                else:
                    # runs have jira ticket
                    # status == all released
                    continue
            else:
                # remind about to-be-deleted runs
                created_date = body["created"]
                url = body["url"]

                created_dt = dt.datetime.strptime(created_date, "%Y-%m-%d")
                duration = today - created_dt

                final_msg.append(
                    f"`/genetics/{seq}/{run}`\n"
                    f"<{jira_url}{key}|{status}> | {assay} | ~{size}GB"
                )
                final_msg.append(
                    f"><{url}|DNANexus Link>\n"
                    f">Created Date: {created_date}\n"
                    f">{duration.days // 7} weeks "
                    f"{duration.days % 7} days ago\n"
                )
                data_count += 1

        if not final_msg:
            log.info("No data to post to Slack")
            return None

        log.info(f"Posting {data_count} runs")

        text_data = "\n".join(final_msg)

        today = get_next_month(today, 1).strftime("%d %b %Y")

        if stale:
            pretext = (
                ":warning: ansible-run-monitoring: "
                f"{data_count} stale runs\n"
                f"genetics usage: {gused}/{gtotal}GB | {gpercent}%"
            )
        else:
            pretext = (
                ":warning: ansible-run-monitoring: "
                f"{data_count} runs that *WILL BE DELETED* on *{today}*\n"
                f"genetics usage: {gused}/{gtotal}GB | {gpercent}%"
            )

        # number above 7,700 seems to get weird truncation
        if len(text_data) < 7700:
            try:
                response = http.post(
                    "https://slack.com/api/chat.postMessage",
                    {
                        "token": token,
                        "channel": f"#{channel}",
                        "attachments": json.dumps(
                            [{"pretext": pretext, "text": text_data}]
                        ),
                    },
                ).json()
                http.close()
            except Exception as e:
                # endpoint request fail from internal server side
                log.error(f"Error sending POST request to channel #{channel}")
                log.error(e)
        else:
            # chunk data based on its length after '\n'.join()
            # if > than 7700 after join(), we append
            # data[start:end-1] into chunks.
            # start = end - 1 and repeat
            chunks = []
            start = 0
            end = 1

            for index in range(1, len(final_msg) + 1):
                chunk = final_msg[start:end]

                if len("\n".join(chunk)) < 7700:
                    end = index

                    if end == len(final_msg):
                        chunks.append(final_msg[start:end])
                else:
                    chunks.append(final_msg[start : end - 1])
                    start = end - 1

            log.info(f"Sending data in {len(chunks)} chunks")

            for chunk in chunks:
                text_data = "\n".join(chunk)

                try:
                    response = http.post(
                        "https://slack.com/api/chat.postMessage",
                        {
                            "token": token,
                            "channel": f"#{channel}",
                            "attachments": json.dumps(
                                [{"pretext": pretext, "text": text_data}]
                            ),
                        },
                    ).json()
                except Exception as e:
                    # endpoint request fail from internal server side
                    log.error(
                        f"Error sending POST request to channel #{channel}"
                    )
                    log.error(e)
            http.close()
    else:
        # simple msg sending
        try:
            response = http.post(
                "https://slack.com/api/chat.postMessage",
                {"token": token, "channel": f"#{channel}", "text": data},
            ).json()

            http.close()

        except Exception as e:
            # endpoint request fail from internal server side
            log.error(f"Error sending POST request to channel #{channel}")
            log.error(e)

    if response["ok"]:
        log.info(f"POST request to channel #{channel} successful")
    else:
        # slack api request failed
        error_code = response["error"]
        log.error(error_code)


def directory_check(directories: list) -> bool:
    """
    Function to check if directory exist
    Mainly to check if /genetic and /var/log/monitoring exist
    Input:
        directories: directory path
    Output: bool
    """

    for dir in directories:
        if os.path.isdir(dir):
            continue
        else:
            log.error(f"{dir} not found")
            return False

    return True


def dx_login(token: str) -> bool:
    """
    Function to check dxpy login
    Input: dxpy token
    Output: boolean
    """

    try:
        DX_SECURITY_CONTEXT = {
            "auth_token_type": "Bearer",
            "auth_token": str(token),
        }

        dx.set_security_context(DX_SECURITY_CONTEXT)
        dx.api.system_whoami()

        return True

    except dx.exceptions.InvalidAuthentication as e:
        log.error(e.error_message())

        return False


def check_project_directory(directory: str) -> bool:
    """
    Function to check if project is in staging52.
    by checking if there's any file returned from that directory
    Input:
        directory: directory path
    Return:
        boolean
    """

    # should return data if there's a file
    # return None if no file
    dx_obj = dx.find_one_data_object(
        zero_ok=True,
        project="project-FpVG0G84X7kzq58g19vF1YJQ",
        folder=f"/{directory}",
    )

    if dx_obj:
        return True

    # check /processed directory in staging52 too
    dx_obj = dx.find_one_data_object(
        zero_ok=True,
        project="project-FpVG0G84X7kzq58g19vF1YJQ",
        folder=f"/processed/{directory}",
    )

    if dx_obj:
        return True

    return False


def get_describe_data(project: str) -> list:
    """
    Function to see if there is 002 project
    and its describe data
    Input:
        project: text
    Return:
        dict of project describe data
    """

    projects = list(
        dx.search.find_projects(
            name=f"002_{project}.*", name_mode="regexp", describe=True, limit=1
        )
    )

    return projects[0] if projects else []


def read_or_new_pickle(path: str) -> dict:
    """
    Read stored pickle memory for the script
    Using defaultdict() automatically create new dict.key()
    Input:
        Path to store the pickle (memory)
    Returns:
        dict: the stored pickle dict
    """
    if os.path.isfile(path):
        with open(path, "rb") as f:
            pickle_dict = pickle.load(f)
    else:
        pickle_dict = collections.defaultdict(dict)
        with open(path, "wb") as f:
            pickle.dump(pickle_dict, f)

    return pickle_dict


def get_next_month(today: dt.datetime, day: int):
    """
    Function to get the next nth datetime
    Input:
        day: target date
    """
    while today.day != day:
        today += dt.timedelta(days=1)

    return today


def get_weekday(date: dt.datetime, day: int, forward: bool = True):
    """
    Function to return datetime of n day of the week
    Input:
        day: day of week (e.g. Friday = 5)
        forward: count forward if True
    """
    while date.isoweekday() != day:
        if forward:
            date += dt.timedelta(days=1)
        else:
            date -= dt.timedelta(days=1)

    return date


def get_runs(seqs: list, gene_path: str, log_path: str):
    """
    Function to check overlap between genetic_dir and log_dir
    Input:
        seqs: list of sequencers
        genetic_dir: path to /genetics
        log_dir: path to all log files
    """
    genetic_directory = []
    logs_directory = []
    tmp_seq = {}

    for sequencer in seqs:
        log.info(f"Loop through {sequencer} started")

        # Defining gene and log directories
        gene_dir = f"{gene_path}/{sequencer}"
        logs_dir = f"{log_path}/{sequencer}"

        # list files in directories
        genetics_num = len(os.listdir(gene_dir))
        logs_num = len(os.listdir(logs_dir))

        log.info(f"{genetics_num} folders in {sequencer} detected")
        log.info(f"{logs_num} logs in {sequencer} detected")

        # Get all files in gene and log dir
        genetic_files = [x.strip() for x in os.listdir(gene_dir)]
        genetic_directory += genetic_files
        logs_directory += [
            x.split(".")[1].strip() for x in os.listdir(logs_dir)
        ]

        for run in genetic_files:
            tmp_seq[run] = sequencer

    return genetic_directory, logs_directory, tmp_seq


def get_date(date: float) -> dt.datetime:
    """
    Function to turn epoch time to datetime
    Input:
        date: epoch
    """
    return dt.datetime.fromtimestamp(date)


def get_duration(today: dt.datetime, date: dt.datetime) -> dt.timedelta:
    """
    Function to get duration (in timedelta) between input date
    and today
    Inputs:
        today: today date
        date: target date
    """
    return today - date


def check_age(date: dt.datetime, today: dt.datetime, week: int) -> bool:
    """
    Function to check input date is older than input week
    Inputs:
        date: input date
        today: today date
        week: ANSIBLE_WEEK
    """
    return date + relativedelta(weeks=+int(week)) < today


def clear_memory(pickle_path: str) -> None:
    """
    Function to erase everything in pickle memory
    Input:
        pickle_path: directory path to pickle
    """

    log.info("Clear pickle")
    with open(pickle_path, "wb") as f:
        pickle.dump(collections.defaultdict(dict), f)


def get_size(path: str) -> float:
    """
    Function to get size of directory
    Taken from https://note.nkmk.me/en/
    Input:
        path: directory path

    Return: bytes -> GB
    """
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_size(entry.path)
    return round(total / 1024 / 1024 / 1024, 2)
