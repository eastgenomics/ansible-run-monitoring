import collections
import datetime as dt
import dxpy as dx
import json
import os
import pickle
import smtplib
import requests

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from os.path import basename
from requests.adapters import HTTPAdapter
from tabulate import tabulate
from urllib3.util import Retry

from .helper import get_logger

log = get_logger("util log")


def post_message_to_slack(
        channel: str,
        token: str,
        message,
        debug: bool,
        today=None,
        slack_url=None,
        notification: bool = False,
        delete: bool = False) -> None:
    """
    Function to send Slack notification
    Inputs:
        channel: egg-alerts etc
        message: str or list
        debug: whether debug mode (channel: egg-test) or not
    Returns:
        dict: slack api response
    """

    log.info(f'Sending POST request to channel: #{channel}')

    http = requests.Session()
    retries = Retry(total=5, backoff_factor=10, method_whitelist=['POST'])
    http.mount("https://", HTTPAdapter(max_retries=retries))

    if debug:
        channel = 'egg-test'

    if not notification:
        try:
            response = http.post('https://slack.com/api/chat.postMessage', {
                'token': token,
                'channel': f'#{channel}',
                'text': message
            }).json()

            http.close()

            if response['ok']:
                log.info(f'POST request to channel #{channel} successful')
                return True
            else:
                # slack api request failed
                error_code = response['error']
                log.error(error_code)
                return False

        except Exception as e:
            # endpoint request fail from internal server side
            log.error(f'Error sending POST request to channel #{channel}')
            log.error(e)
            return False
    else:
        data = []

        for run, _, status, key in message:
            data.append(f'<{slack_url}{key}|{run}> with status `{status}`')

        text_data = '\n'.join(data)

        today = get_next_month(today).strftime("%d %b %Y")

        if delete:
            pretext = (
                'ansible-run-monitoring: '
                'These runs have been deleted'
            )
        else:
            pretext = (
                'ansible-run-monitoring: '
                f'runs that will be deleted on {today}'
            )

        # number above 7,995 seems to get truncation
        if len(text_data) < 7995:

            response = http.post(
                'https://slack.com/api/chat.postMessage', {
                    'token': token,
                    'channel': f'#{channel}',
                    'attachments': json.dumps([{
                        "pretext": pretext,
                        "text": text_data}])
                }).json()

            http.close()

            if response['ok']:
                log.info(f'POST request to channel #{channel} successful')
                return True
            else:
                # slack api request failed
                error_code = response['error']
                log.error(error_code)
                return False
        else:
            # chunk data based on its length after '\n'.join()
            # if > than 7,995 after join(), we append
            # data[start:end-1] into chunks.
            # start = end - 1 and repeat
            chunks = []
            start = 0
            end = 1

            for index in range(1, len(data) + 1):
                chunk = data[start:end]

                if len('\n'.join(chunk)) < 7995:
                    end = index

                    if end == len(data):
                        chunks.append(data[start:end])
                else:
                    chunks.append(data[start:end-1])
                    start = end - 1

            log.info(f'Sending data in {len(chunks)} chunks')

            for chunk in chunks:
                text_data = '\n'.join(chunk)

                response = http.post(
                    'https://slack.com/api/chat.postMessage', {
                        'token': token,
                        'channel': f'#{channel}',
                        'attachments': json.dumps([{
                            "pretext": pretext,
                            "text": text_data}])
                    }).json()

                if response['ok']:
                    log.info(f'POST request to channel #{channel} successful')
                    continue
                else:
                    error_code = response['error']
                    log.error(error_code)

            http.close()

            return True


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
            log.error(f'{dir} not found')
            return False

    return True


def dx_login(token: str) -> bool:

    """
    Function to check dxpy login
    Input: dxpy token
    Output: boolean
    """

    # try to get auth token from env (i.e. run in docker)
    try:
        DX_SECURITY_CONTEXT = {
            "auth_token_type": "Bearer",
            "auth_token": token
        }

        dx.set_security_context(DX_SECURITY_CONTEXT)
        dx.api.system_whoami()

        return True

    except Exception as error:
        log.error(error)

        return False


def check_project_directory(project: str, token: str) -> bool:

    """
    Function to check if project is in staging52.
    Input:
        project: directory path
    Return:
        boolean
    """

    if not dx_login(token):
        return False

    dx_obj = list(dx.find_data_objects(
        project='project-FpVG0G84X7kzq58g19vF1YJQ',
        folder=f'/{project}',
        limit=1)
    )

    if dx_obj:
        return True

    dx_obj = list(dx.find_data_objects(
        project='project-FpVG0G84X7kzq58g19vF1YJQ',
        folder=f'/processed/{project}',
        limit=1)
    )

    if dx_obj:
        return True

    return False


def get_describe_data(project: str, token: str) -> list:

    """
    Function to see if there is 002 project
    and its describe data
    Input:
        project: text
    Return:
        dict of project describe data
    """

    if not dx_login(token):
        return False

    dxes = list(dx.search.find_projects(
        name=f'002_{project}.*',
        name_mode="regexp",
        describe=True,
        limit=1
        ))

    return dxes[0] if dxes else []


def send_mail(
        send_from: str,
        send_to: list,
        subject: str,
        server: str,
        port: int,
        df=None,
        files=None) -> None:

    """
    Function to send server email.
    Inputs:
        send_from: str
        send_to: list
        subject: text
        df: DataFrame or None
        files: list
    """

    assert isinstance(send_to, list)

    # email messge content
    text = """
        Here's the data for duplicated runs found in
        "/genetics" & "/var/log/dx-streaming-uploads" & DNAnexus:

        {table}

        Kind Regards,
        Beep Robot

    """

    html = """
        <html>
        <head>
        <style>
        table, th, td {{ border: 1px solid black; border-collapse: collapse; }}
        th, td {{ padding: 5px; }}
        </style>
        </head>
        <body>
        <p>
        Here's the data for duplicated runs found in
        "/genetics" & "/var/log/dx-streaming-uploads" & DNAnexus:
        </p>
        {table}
        <p>Kind Regards</p>
        <p>Beep Robot~</p>
        </body></html>
    """

    if df is not None:
        # we make df into table in email using tabulate

        col_header = list(df.columns.values)
        text = text.format(table=tabulate(
            df,
            headers=col_header,
            tablefmt="grid"))

        html = html.format(table=tabulate(
            df,
            headers=col_header,
            tablefmt="html"))

        msg = MIMEMultipart(
            "alternative", None, [MIMEText(text), MIMEText(html, 'html')])

    # email headers
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    # email message attachment (default: None)
    for f in files or []:
        with open(f, "rb") as fil:
            part = MIMEApplication(
                fil.read(),
                Name=basename(f)
            )
        # After the file is closed
        part['Content-Disposition'] = 'attachment; filename="%s"' % basename(f)
        msg.attach(part)

    try:
        smtp = smtplib.SMTP(server, port)

        log.info(f'Sending email to {COMMASPACE.join(send_to)}')
        smtp.sendmail(send_from, send_to, msg.as_string())
        log.info(f'Email to {COMMASPACE.join(send_to)} SENT')

        smtp.quit()

    except Exception as e:
        log.error(f'Send email function failed with error: {e}')
        message = (
            "Ansible-Monitoring: ERROR sending to helpdesk! Error Code: \n"
            f"`{e}`"
            )

        post_message_to_slack('egg-alerts', message)


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
        with open(path, 'rb') as f:
            pickle_dict = pickle.load(f)
    else:
        pickle_dict = collections.defaultdict(list)
        with open(path, 'wb') as f:
            pickle.dump(pickle_dict, f)

    return pickle_dict


def get_next_month(today):
    """
    Function to get the next automated-archive run date
    Input:
        today (Datetime)
    Return (Datetime):
        If today.day is between 1-15: return 15th of this month
        If today.day is after 15: return 1st day of next month
    """

    while today.day != 1:
        today += dt.timedelta(days=1)

    return today


def get_runs(seqs: list, genetic_dir: str, log_dir: str, tmp_seq: dict = {}):
    """
    Function to check overlap between genetic_dir and log_dir
    Input:
        seqs: list of sequencers
        genetic_dir: path to /genetics
        log_dir: path to all the log files
    """
    genetic_directory = []
    logs_directory = []

    for sequencer in seqs:
        log.info(f'Loop through {sequencer} started')

        # Defining gene and log directories
        gene_dir = f'{genetic_dir}/{sequencer}'
        logs_dir = f'{log_dir}/{sequencer}'

        # Get all files in gene and log dir
        genetic_files = [x.strip() for x in os.listdir(gene_dir)]
        genetic_directory += genetic_files
        logs_directory += [
            x.split('.')[1].strip() for x in os.listdir(logs_dir)]

        for run in genetic_files:
            tmp_seq[run] = sequencer

        genetics_num = len(os.listdir(gene_dir))
        logs_num = len(os.listdir(logs_dir))

        log.info(f'{genetics_num} folders in {sequencer} detected')
        log.info(f'{logs_num} logs in {sequencer} detected')

    return genetic_directory, logs_directory, tmp_seq


def check_age(data: dict, today, week: int):
    """
    Function to check if project describe() date
    is old enough (duration to today's date is > week)
    Inputs:
        data: project describe() data
        today: DateTime (today's date)
        week: ANSIBLE_WEEK
    """
    # convert millisec from Epoch datetime to readable human format
    created_date = dt.datetime.fromtimestamp(
        data['created'] / 1000.0)
    created_on = created_date.strftime('%Y-%m-%d')

    duration = today - created_date

    # check if created_date is more than ANSIBLE_WEEK week(s)
    # duration (sec) / 60 to minute / 60 to hour / 24 to days
    # If total days is > 7 days * 6 weeks
    old_enough = duration.total_seconds() / (
        24*60*60) > 7 * int(week)

    return old_enough, created_on, duration


def clear_memory(pickle_path: str) -> None:
    """
    Function to erase everything in pickle
    """
    d = read_or_new_pickle(pickle_path)

    d['runs'] = []

    log.info('Writing into pickle file')
    with open(pickle_path, 'wb') as f:
        pickle.dump(d, f)
