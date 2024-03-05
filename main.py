import argparse
import collections
from datetime import datetime
import os
import pickle
import shutil
import sys
from types import SimpleNamespace

from bin.util import (
    post_message_to_slack,
    post_simple_message_to_slack,
    check_project_directory,
    check_age,
    directory_check,
    dx_login,
    read_or_new_pickle,
    clear_memory,
    get_next_month,
    get_weekday,
    get_describe_data,
    get_size,
    get_date,
    get_duration,
    get_runs,
)

from bin.helper import get_logger
from bin.jira import Jira

log = get_logger("main log")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--notification", action="store_true")

    return parser.parse_args()


def get_env_variables():
    """
    Get required environment variables for running

    Returns
    -------
    SimpleNamespace
        mapping of key names to selected environment variables

    Raises
    ------
    AssertionError
        Raised if one or more variables missing
    """
    env_variable_mapping = {
        "slack_token": "SLACK_TOKEN",
        "debug": "ANSIBLE_DEBUG",
        "server_testing": "ANSIBLE_TESTING",
        "genetics_dir": "ANSIBLE_GENETICDIR",
        "logs_dir": "ANSIBLE_LOGSDIR",
        "ansible_week": "ANSIBLE_WEEK",
        "pickle_path": "ANSIBLE_PICKLE_PATH",
        "dnanexus_token": "DNANEXUS_TOKEN",
        "jira_token": "JIRA_TOKEN",
        "jira_email": "JIRA_EMAIL",
        "jira_api_url": "JIRA_API_URL",
        "slack_url": "SLACK_NOTIFY_URL",
        "jira_project_id": "JIRA_PROJECT_ID",
        "jira_reporter_id": "JIRA_REPORTER_ID"
    }

    selected_env = SimpleNamespace()
    missing = []

    for k, v in env_variable_mapping.items():
        if not os.environ.get(v):
            missing.append(v)
        else:
            selected_env.k = os.environ.get(v)

    assert not missing, (
        f"Error - missing one or more environment variables "
        f"{', '.join(missing)}"
    )

    return selected_env


def check_for_deletion(
        seqs,
        genetics_dir,
        logs_dir,
        ansible_week,
        server_testing,
        slack_token,
        pickle_file,
        debug,
        jira_assay,
        jira_url,
        jira

    ):
    """
    Check for runs to delete, will be called every Monday and check for
    runs that are over X weeks old

    Inputs
    ------
    seqs : list
        list of sequencer IDs to check runs against
    genetics_dir : str
        parent path to run directories
    logs_dir : str
        parent path to dx-streaming-upload log directory
    ansible_week : int
        number of weeks at which to automatically delete a run
    server_testing : bool(?)
    slack_token : str
        Slack API token
    pickle_file : str
        name of pickle file to write runs to delete to
    debug : bool
        If running in debug
    jira_assay : list
        list of Jira assay codes we automatically delete runs for
    jira_url : ?

    jira

    Outputs
    -------
    file
        pickle file with details on runs to automatically delete store in
    """
    to_delete = collections.defaultdict(dict)  # to store runs marked for deletion
    manual_review = []  # to store runs that need manually reviewing

    genetic_directory, logs_directory, tmp_seq = get_runs(
        seqs, genetics_dir, logs_dir
    )

    # get /genetic disk usage stat
    init_usage = shutil.disk_usage(genetics_dir)
    today = datetime.today()

    # Get the duplicates between two directories /genetics & /var/log/ =>
    # valid sequencing runs that dx-streaming-upload has uploaded
    uploaded_runs = set(genetic_directory) & set(logs_directory)

    log.info(f"Found {len(uploaded_runs)} run directories")

    for run in uploaded_runs:
        # check if proj in staging52
        uploaded: bool = check_project_directory(run)

        # get the sequencer the proj is in
        seq = tmp_seq[run]

        # get run size
        run_path = f"{genetics_dir}/{seq}/{run}"
        run_size = get_size(run_path)

        # get 002 project describe data
        project_data = get_describe_data(run)

        if project_data:
            # found 002 project => generate link
            trimmed_id = project_data.get(
                'describe', '').get('id', '').replace('project-', '')
            url = (
                f"https://platform.dnanexus.com/panx/projects/"
                f"{trimmed_id}/data"
            )
        else:
            url = "NA"

        # get run created date
        created_date = get_date(os.path.getmtime(run_path))
        created_on = created_date.strftime("%Y-%m-%d")
        duration = get_duration(today, created_date)

        # check age of run
        old_enough = check_age(created_date, today, ansible_week)

        # get run Jira details
        assay, status, key = jira.get_issue_detail(run, server_testing)

        delete = False

        if not old_enough:
            # run less than defined no. weeks to wait to delete => skip
            log.info(
                f"{project} {created_on} ::: {round(duration.days / 7, 2)}"
                f" weeks - not old enough to delete"
            )

            continue

        if uploaded:
            # found uploaded run in StagingArea52 => check it is has
            # been processed and Jira state
            if (
                project_data and
                status.upper() == "ALL_SAMPLES_RELEASED"
                and assay in jira_assay
            ):
                # run has been released and is an assay we automatically
                # delete => flag for deletion
                log.info(
                    f"{project} {created_on} ::: {round(duration.days / 7, 2)}"
                    f" weeks - flagged for deletion"
                )

                delete = True
            elif (
                status.upper() in [
                    "DATA CANNOT BE PROCESSED", "DATA CANNOT BE RELEASED"
                ] and
                assay in jira_assay
            ):
                # run uploaded and is an assay we automatically delete
                # but either can't be processed or was processed but not
                # released (i.e. low quality) => flag these to delete
                log.info(
                    f"{project} {created_on} ::: {round(duration.days / 7, 2)}"
                    f" weeks - uploaded but not processed / released - "
                    "flagged for deletion"
                )
                delete = True


        if delete:
            # enough criteria passed above to delete
            to_delete[run] = {
                "seq": seq,
                "status": status,
                "key": key,
                "assay": assay,
                "created": created_on,
                "duration": round(duration.days / 7, 2),
                "old_enough": old_enough,
                "url": url,
                "size": run_size,
            }
        else:
            # run old enough to delete but not passed checks => flag
            # up to review manually
            log.info(
                f"{project} {created_on} ::: {round(duration.days / 7, 2)}"
                f" weeks - run not passed checks - flag for manual review"
            )

            manual_review[run] = {
                "seq": seq,
                "status": status,
                "key": key,
                "assay": assay,
                "created": created_on,
                "duration": round(duration.days / 7, 2),
                "old_enough": old_enough,
                "url": url,
                "size": run_size,
            }

    if to_delete:
        # found more than one run to delete
        log.info("Writing runs flagged to delete into pickle file")
        with open(pickle_file, "wb") as f:
            pickle.dump(to_delete, f)

    if manual_review:
        # found more than one run requiring manually reviewing
        post_message_to_slack(
            channel="egg-alerts",
            token=slack_token,
            data=manual_review,
            debug=debug,
            usage=init_usage,
            today=today,
            jira_url=jira_url,
            action="manual",
        )


def delete_runs(
        pickle,
        genetics_dir,
        jira_project_id,
        jira_reporter_id,
        slack_token,
        server_testing,
        debug,
        jira
    ):
    """
    Delete the specified runs in the pickle file

    Inputs
    ------
    pickle : str
        pickle file with runs to be deleted
    genetics_dir : str
        parent dir of sequencing runs
    jira_project_id : str
        ID of Jira project
    jira_reporter_id : str
        ID reporting to Jira as
    slack_token : str
        Slack API token
    server_testing : bool
        controls if running test
    debug : bool
        controls debug level
    jira : Jira
        jira.Jira object
    """
    deleted_details = dict()
    deleted_runs = []

    # allowed states for Jira tickets to be in for automated deletion
    jira_delete_status = [
        "ALL_SAMPLES_RELEASED",
        "DATA CANNOT BE PROCESSED",
        "DATA CANNOT BE RELEASED"
    ]

    # get /genetic disk usage stat
    init_usage = shutil.disk_usage(genetics_dir)
    today = datetime.today()

    runs_pickle = read_or_new_pickle(pickle)

    if not runs_pickle:
        # pickle file empty or doesn't exist => exit
        log.info("pickle file empty or doesn't exist. Exiting now.")
        sys.exit(0)

    for run, values in runs_pickle.items():
        # last check to see if Jira status is still valid for deleting
        _, status, _ = jira.get_issue_detail(run, server_testing)

        seq = values["seq"].strip()
        key = values["key"].strip()
        assay = values["assay"].strip()
        size = values["size"].strip()

        if status.upper() not in jira_delete_status:
            log.info(
                f"Jira status not valid to delete ({status}) - skipping "
                f"deletion of {genetics_dir}/{seq}/{run}")
            continue

        deleted_runs.append(f"{genetics_dir}/{seq}/{run} {today}\n")

        try:
            log.info(f"DELETING {genetics_dir}/{seq}/{run}")
            shutil.rmtree(f"{genetics_dir}/{seq}/{run}")

            deleted_details[run] = {
                "seq": seq,
                "status": status,
                "key": key,
                "assay": assay,
                "size": size
            }
        except OSError as err:
            log.error(
                f"Error in deleting {genetics_dir}/{seq}/{run}. Stopping "
                "further automatic deletion"
            )

            clear_memory(pickle)

            msg = (
                ":warning:"
                f"ANSIBLE-MONITORING: ERROR with deleting `{run}`."
                " Stopping further automatic deletion."
                f"\n```{err}```"
            )

            post_simple_message_to_slack(
                msg,
                "egg-alerts",
                slack_token,
                debug,
            )

            sys.exit("END SCRIPT")

    if deleted_details:
        # something deleted => create Jira ticket to acknowledge

        # get after deletion disk usage
        post_usage = shutil.disk_usage(genetics_dir)
        # make datetime into str type
        jira_date = today.strftime("%d/%m/%Y")

        # format disk usage for jira issue description
        init_total = round(init_usage[0] / 1024 / 1024 / 1024, 2)
        init_used = round(init_usage[1] / 1024 / 1024 / 1024, 2)
        init_percent = round((init_usage[1] / init_usage[0]) * 100, 2)

        p_total = round(post_usage[0] / 1024 / 1024 / 1024, 2)
        p_used = round(post_usage[1] / 1024 / 1024 / 1024, 2)
        p_percent = round((post_usage[1] / post_usage[0]) * 100, 2)

        # format deleted run for issue description
        jira_data = [
            f"{k} in /genetics/{v['seq']}" for k, v in deleted_details.items()
        ]

        # description body
        body = "\n".join(jira_data)

        desc = f"Runs deleted on {jira_date}\n"

        # all disk space data
        disk_usage = (
            "\n/genetics disk usage before: "
            f"{init_used} / {init_total} {init_percent}%"
            "\n/genetics disk usage after: "
            f"{p_used} / {p_total} {p_percent}%"
        )

        desc += body + disk_usage

        # create Jira issue
        # issue type for acknowledgement 10124
        # helpdesk 10042 for debug 10040 for prod

        log.info("Creating Jira acknowledgement issue")
        issue_title = f"{jira_date} Automated deletion of runs from ansible server"
        response = jira.create_issue(
            summary=issue_title,
            issue_id=10124,
            project_id=jira_project_id,
            reporter_id=jira_reporter_id,
            priority_id=3,
            desc=desc,
            assay=False,
        )

        if "id" in response:
            # log the raised issue key for reference in future
            issue_key = response["key"]
            log.info(f"{issue_key} {jira_project_id}")
        else:
            # if jira ticket creation issue
            # send msg to Slack - stop script
            err_msg = response["errors"]
            msg = ":warning:" "ANSIBLE-MONITORING: ERROR with creating Jira ticket!"
            msg += f"\n`{err_msg}`"

            post_simple_message_to_slack(
                msg,
                "egg-alerts",
                slack_token,
                debug,
            )

            log.error(response)
            sys.exit("END SCRIPT")


    # write to /log just for own record
    with open("/log/monitoring/ansible_delete.txt", "a") as f:
        for deleted in deleted_runs:
            f.write(deleted)



def main():
    args = parse_arguments()
    env = get_env_variables()

    # log debug status
    if env.debug:
        log.info("Running in debug mode")
        env.pickle_path = f"{env.pickle_path}/ansible_dict.test.pickle"
    else:
        log.info("Running in PRODUCTION mode")
        env.pickle_path = f"{env.pickle_path}/ansible_dict.pickle"

    # dxpy login
    if not dx_login(env.dnanexus_token):
        message = ":warning:ANSIBLE-RUN-MONITORING: ERROR with dxpy login!"

        post_simple_message_to_slack(
            message,
            "egg-alerts",
            env.slack_token,
            env.debug,
        )

        sys.exit("END SCRIPT")

    # check if /genetics & /logs/dx-streaming-upload exist
    if not directory_check([env.genetics_dir, env.logs_dir]):
        message = ":warning:ANSIBLE-MONITORING: ERROR with missing directory!"

        post_simple_message_to_slack(
            message,
            "egg-alerts",
            env.slack_token,
            env.debug,
        )

        sys.exit("END SCRIPT")

    # get script run date
    today = datetime.today()
    log.info(today)

    jira = Jira(
        token=env.jira_token,
        email=env.jira_email,
        api_url=env.jira_api_url,
        debug=env.debug
    )

    if today.isoweekday == 1:
        # Monday => check for runs to delete and send upcoming alert
        check_for_deletion(
            seqs=env.seqs,
            genetics_dir=env.genetics_dir,
            logs_dir=env.ogs_dir,
            ansible_week=env.ansible_week,
            server_testing=env.server_testing,
            slack_token=env.slack_token,
            pickle_file=env.pickle_file,
            debug=env.debug,
            jira=jira,
            jira_assay=env.jira_assay,
            jira_url=env.jira_url
        )
    elif today.isoweekday == 3:
        # Wednesday => run the deletion
        delete_runs(
            pickle=env.pickle_file,
            genetics_dir=env.genetics_dir,
            jira_project_id=env.jira_project_id,
            jira_reporter_id=env.jira_reporter_id,
            slack_token=env.slack_token,
            server_testing=env.server_testing,
            debug=env.debug,
            jira=jira
        )

    else:
        # other day of the week => do nothing
        log.info(
            f"Today is not Monday or Wednesday - nothing to do"
        )
        sys.exit(0)


if __name__ == "__main__":
    log.info("STARTING SCRIPT")
    main()
    log.info("END SCRIPT")
