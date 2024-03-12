from datetime import datetime
import os
import pickle
import shutil
import sys
from types import SimpleNamespace

from bin.util import (
    post_message_to_slack,
    post_simple_message_to_slack,
    check_run_uploaded,
    check_age,
    directory_check,
    dx_login,
    read_or_new_pickle,
    clear_memory,
    get_describe_data,
    get_size,
    get_date,
    get_duration,
    get_runs,
)

from bin.helper import get_logger
from bin.jira import Jira

log = get_logger("main log")


def get_env_variables() -> SimpleNamespace:
    """
    Get required environment variables for running and store
    these in a NameSpace object

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
        "slack_url": "SLACK_NOTIFY_JIRA_URL",
        "dnanexus_token": "DNANEXUS_TOKEN",
        "jira_token": "JIRA_TOKEN",
        "jira_email": "JIRA_EMAIL",
        "jira_url": "JIRA_API_URL",
        "jira_assay": "JIRA_ASSAY",
        "jira_project_id": "JIRA_PROJECT_ID",
        "jira_reporter_id": "JIRA_REPORTER_ID",
        "pickle_file": "ANSIBLE_PICKLE_PATH",
        "genetics_dir": "ANSIBLE_GENETICDIR",
        "logs_dir": "ANSIBLE_LOGSDIR",
        "ansible_week": "ANSIBLE_WEEK",
        "seqs": "ANSIBLE_SEQ",
        "server_testing": "ANSIBLE_TESTING",
        "debug": "ANSIBLE_DEBUG"
    }

    parsed = {}
    missing = []

    for key, value in env_variable_mapping.items():
        if not os.environ.get(value):
            missing.append(value)
        else:
            parsed[key] = os.environ.get(value)

    selected_env = SimpleNamespace(**parsed)


    assert not missing, (
        f"Error - missing one or more environment variables "
        f"{', '.join(missing)}"
    )

    # fix required types
    selected_env.seqs = selected_env.seqs.split(',')
    selected_env.jira_assay = selected_env.jira_assay.split(',')
    selected_env.server_testing = (
        True if selected_env.server_testing.lower() == 'true' else False
    )
    selected_env.debug = (
        True if selected_env.debug.lower() == 'true' else False
    )
    selected_env.ansible_week = int(selected_env.ansible_week)

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
    ) -> None:
    """
    Check for runs to delete, will be called everyday but and check for
    runs that can be automatically deleted against the following criteria:

        - over X weeks old (defined from config)
        - have data in StagingArea52 DNAnexus project
        - have a 002 project
        - have a Jira ticket with stats in one of the following:
            - ALL_SAMPLES_RELEASED
            - DATA CANNOT BE PROCESSED
            - DATA CANNOT BE RELEASED

    Any runs that are old enough but do not meet the above criteria will
    be added to a Slack alert for manual review. The pickle file will
    only be updated on a Monday ahead of deletion on the Wednesday

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
    jira_url : str
        URL endpoint for our Jira
    jira : jira.Jira
        Jira class object for querying Jira

    Outputs
    -------
    file
        pickle file with details on runs to automatically delete store in
    """
    to_delete = {}  # to store runs marked for deletion
    manual_review = {}  # to store runs that need manually reviewing

    genetic_directory, logs_directory, tmp_seq = get_runs(
        seqs, genetics_dir, logs_dir
    )

    # get /genetic disk usage stat
    init_usage = shutil.disk_usage(genetics_dir)
    today = datetime.today()

    # Get the duplicates between two directories /genetics & /var/log/ =>
    # valid sequencing runs that dx-streaming-upload has uploaded
    local_runs = sorted(set(genetic_directory) & set(logs_directory))

    log.info(f"Found {len(local_runs)} run directories")

    for run in local_runs:
        log.info(f"Checking state of {run}")
        # check if run in stagingArea52 DNAnexus project
        uploaded = check_run_uploaded(run)

        # get the sequencer the run is from
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

        log.info(
            f"Following data found: old enough: {old_enough}; uploaded: "
            f"{uploaded}; 002 project: {url}; Jira status: {status}"
        )

        if not old_enough:
            # run less than defined no. weeks to wait to delete => skip
            log.info(
                f"{run} {created_on} ::: {round(duration.days / 7, 2)}"
                f" weeks - not old enough to delete"
            )

            continue

        if uploaded:
            # found uploaded run in StagingArea52 => check it is has
            # been processed and Jira state
            if (
                project_data and
                status.upper() == "ALL SAMPLES RELEASED"
                and assay in jira_assay
            ):
                # run has been released and is an assay we automatically
                # delete => flag for deletion
                log.info(
                    f"{run} {created_on} ::: {round(duration.days / 7, 2)}"
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
                    f"{run} {created_on} ::: {round(duration.days / 7, 2)}"
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
                "uploaded": uploaded,
                "project": project_data,
                "old_enough": old_enough,
                "url": url,
                "size": run_size
            }
        else:
            # run old enough to delete but not passed checks => flag
            # up to review manually
            log.info(
                f"{run} {created_on} ::: {round(duration.days / 7, 2)}"
                f" weeks - run not passed checks - flag for manual review"
            )

            manual_review[run] = {
                "seq": seq,
                "status": status,
                "uploaded": uploaded,
                "project": project_data,
                "key": key,
                "assay": assay,
                "created": created_on,
                "duration": round(duration.days / 7, 2),
                "old_enough": old_enough,
                "url": url,
                "size": run_size,
            }

    if to_delete and today.isoweekday() == 1:
        # found more than one run to delete and today is Monday =>
        # update the pickle file for deletion on Wednesday
        log.info("Writing runs flagged to delete into pickle file")
        with open(pickle_file, "wb") as f:
            pickle.dump(to_delete, f)

        # alert us that some runs will be deleted on the next Wednesday
        post_message_to_slack(
            channel="egg-test",
            token=slack_token,
            data=to_delete,
            debug=debug,
            n_weeks=ansible_week,
            usage=init_usage,
            today=today,
            jira_url=jira_url,
            action="delete",
        )

    if manual_review and today.isoweekday() == 1:
        # found more than one run requiring manually reviewing, only
        # send alerts for these on a Monday morning to not get too spammy
        print('posting slack')
        post_message_to_slack(
            channel="egg-test",
            token=slack_token,
            data=manual_review,
            debug=debug,
            n_weeks=ansible_week,
            usage=init_usage,
            today=today,
            jira_url=jira_url,
            action="manual",
        )


def delete_runs(
        pickle_file,
        genetics_dir,
        jira_project_id,
        jira_reporter_id,
        slack_token,
        server_testing,
        debug,
        jira
    ) -> None:
    """
    Delete the specified runs in the pickle file that have been
    previously checked and flagged for automatic deletion

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
        "ALL SAMPLES RELEASED",
        "DATA CANNOT BE PROCESSED",
        "DATA CANNOT BE RELEASED"
    ]

    # get /genetic disk usage stat
    init_usage = shutil.disk_usage(genetics_dir)
    today = datetime.today()

    if today.isoweekday() != 3:
        # today is not a Wednesday => don't do anything
        log.info(
            f"Today is {today.strftime('%A')} therefore no "
            "deletion will be performed"
        )

        return

    runs_pickle = read_or_new_pickle(pickle_file)

    if not runs_pickle:
        # pickle file empty or doesn't exist => exit
        log.info(
            f"pickle file {pickle_file} empty or doesn't exist, nothing "
            "to delete. Exiting now."
        )
        sys.exit(0)

    for run, values in runs_pickle.items():
        # last check to see if Jira status is still valid for deleting
        _, status, _ = jira.get_issue_detail(run, server_testing)

        seq = values["seq"].strip()
        key = values["key"].strip()
        assay = values["assay"].strip()
        size = str(values["size"]).strip()

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
                "further automatic deletion."
            )

            clear_memory(pickle_file)

            msg = (
                ":warning:"
                f"ANSIBLE-MONITORING: ERROR with deleting `{run}`."
                " Stopping further automatic deletion."
                f"\n```{err}```"
            )

            post_simple_message_to_slack(
                message=msg,
                channel="egg-alerts",
                slack_token=slack_token,
                debug=debug,
            )

            sys.exit("END SCRIPT")

    if deleted_details:
        # something deleted => create Jira ticket to acknowledge

        # get after deletion disk usage
        post_usage = shutil.disk_usage(genetics_dir)
        # make datetime into str type
        jira_date = today.strftime("%d/%m/%Y")

        # format disk usage for Jira issue description
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
    if os.path.exists("/log/monitoring"):
        log_file = "/log/monitoring/ansible_delete.txt"
    else:
        log_file = "ansible_delete.txt"

    with open(log_file, "a") as f:
        for deleted in deleted_runs:
            f.write(deleted)


def main():
    print('starting')
    env = get_env_variables()

    # log debug status
    if env.debug:
        log.info("Running in debug mode")
        env.pickle_file = f"{env.pickle_file}/ansible_dict.test.pickle"
    else:
        log.info("Running in PRODUCTION mode")
        env.pickle_file = f"{env.pickle_file}/ansible_dict.pickle"

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
        api_url=env.jira_url,
        debug=env.debug
    )

    check_for_deletion(
        seqs=env.seqs,
        genetics_dir=env.genetics_dir,
        logs_dir=env.logs_dir,
        ansible_week=env.ansible_week,
        server_testing=env.server_testing,
        slack_token=env.slack_token,
        pickle_file=env.pickle_file,
        debug=env.debug,
        jira=jira,
        jira_assay=env.jira_assay,
        jira_url=env.jira_url
    )

    delete_runs(
        pickle_file=env.pickle_file,
        genetics_dir=env.genetics_dir,
        jira_project_id=env.jira_project_id,
        jira_reporter_id=env.jira_reporter_id,
        slack_token=env.slack_token,
        server_testing=env.server_testing,
        debug=env.debug,
        jira=jira
    )


if __name__ == "__main__":
    log.info("STARTING SCRIPT")
    main()
    log.info("END SCRIPT")
