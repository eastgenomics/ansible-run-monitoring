"""
Outline of end to end test to set up

Runs with the following:
    - 1 run under X weeks old
        - these should be logged as not old enough and excluded
    - Runs criteria that should be logged as error and flagged for manual review
        - 1 run old enough but no data uploaded (shouldn't happen)
        - 1 run run old enough and uploaded to stagingArea52 but no 002 project
        - 1 run old enough, uploaded and 002 project but ticket not in right state
    - 1 run that is old enough, uploaded, 002 project and ticket released
        - flagged to delete
    - 1 run that is old enough but has failed sequencing (ticket moved to
        CANNOT BE PROCESSED)
        - flagged to delete
    1 run that is old enough and processed but likely QC failed (ticket
        moved to CANNOT BE RELEASED)
        - flagged to delete


The above needs to be tested on following days of the week:
    - Monday
        - run deletion check, create pickle file of runs to delete
        - should send alert of runs above with the given issues and
            add these to the logs
    - Wednesday
        - should run the deletion against runs in the pickle file
    - other days of the week
        - should log issues but not send notifications

"""
from calendar import day_name
from datetime import datetime
import os
from pathlib import Path
import shutil
import sys
import traceback
from unittest.mock import Mock, patch

from dateutil.relativedelta import relativedelta
from faker import Faker

from bin.jira import Jira
import monitor


# suffix for random naming of test runs
SUFFIX = ""


def create_test_run_directories() -> None:
    """
    Create test run data structure of 7 runs, all but the first we're
    setting to be 'old enough' to delete (i.e. > ANSIBLE WEEKS old)
    """
    run_directories = [
        f"seq1/run1_{SUFFIX}",
        f"seq1/run2_{SUFFIX}",
        f"seq1/run3_{SUFFIX}",
        f"seq2/run4_{SUFFIX}",
        f"seq2/run5_{SUFFIX}",
        f"seq2/run6_{SUFFIX}",
        f"seq2/run7_{SUFFIX}",
    ]

    os.makedirs("simulate_test", exist_ok=True)

    today = datetime.today()

    for idx, run in enumerate(run_directories, 2):
        os.makedirs(f"simulate_test/{run}", exist_ok=True)

        with open(f"simulate_test/{run}/test.file", "wb") as f:
            # create test file of 1GB without actually writing any data to disk
            f.truncate(1024 * 1024 * 1024)

        # set run age to be sequentially 1 week older starting at 2 weeks old
        age = (today + relativedelta(weeks=-idx)).timestamp()
        os.utime(f"simulate_test/{run}", (age, age))


def create_test_logs() -> None:
    """
    Create required log files as generated from dx-streaming-upload, these
    are used to checking if a directory is an monitored run directory
    that we have started at least uploading
    """
    os.makedirs("simulate_test/logs/seq1", exist_ok=True)
    os.makedirs("simulate_test/logs/seq2", exist_ok=True)

    for idx in range(0, 8):
        open(
            f"simulate_test/logs/seq1/"
            f"run.run{idx}_{SUFFIX}.lane.all.log", "w"
        ).close()


def create_jira_tickets(jira) -> list:
    """
    Create required Jira tickets in required states for each run, this
    will be as follows:
        - run1 = not old enough -> NEW
        - run2 = not uploaded -> NEW
        - run3 = not processed -> New
        - run4 = ticket not in right state -> On Hold
        - run5 = released -> All Samples Released
        - run6 = failed - not processed -> Data cannot be processed
        - run7 = bad QC - not released -> Data cannot be released

    Parameters
    ----------
    jira : jira.Jira
        Jira object for Jira queries

    # token : string
    #     Jira API token
    # email : string
    #     Atlassian account email
    # url : string
    #     URL endpoint for test helpdesk
    """
    # mapping of run name to Jira issue state, these are numerical IDs
    # associated to each state that we need to transition each ticket
    # through, these can be found by going into the workflow edit mode
    ticket_states = {
        f"run1_{SUFFIX}": None,
        f"run2_{SUFFIX}": None,
        f"run3_{SUFFIX}": None,
        f"run4_{SUFFIX}": None,
        f"run5_{SUFFIX}": [31, 41, 21],  # Data released
        f"run6_{SUFFIX}": [31, 61],      # Data cannot be processed
        f"run7_{SUFFIX}": [31, 41, 71]   # Data cannot be released
    }

    created_issues = []

    for run, state in ticket_states.items():
        print(f"Creating Jira issue for {run}")
        issue = jira.create_issue(
            summary=run,
            issue_id=10179,    # issue type
            project_id=10042,  # EBHD id
            reporter_id="5c0e8b8d53cd043c8c6149eb",
            priority_id=3,
            desc="Ticket created as part of simulated testing of automated deletion",
            assay=True,
        )

        created_issues.append(issue)
        if state:
            for transition in state:
                jira.make_transition(
                    issue_id=issue['id'],
                    transition_id=transition
                )

    return created_issues


def create_run_suffix() -> None:
    """
    Generate random words to append to run ID to get a random name,
    dumping this into globals for every time it is called as too lazy
    to go back and pass it around
    """
    fake = Faker()
    global SUFFIX
    SUFFIX='_'.join([fake.word() for x in range(3)])


def delete_test_data() -> None:
    """
    Check for test data directories and pickle file to clean up
    """
    print("Cleaning up test data directories")
    if os.path.exists('simulate_test'):
        shutil.rmtree('simulate_test')


def delete_pickle() -> None:
    """
    Delete the saved pickle file
    """
    if os.path.exists("check.pkl"):
        os.remove("check.pkl")


def delete_jira_tickets(jira, issues) -> None:
    """
    Delete Jira issue tickets we created as part of testing

    Parameters
    ----------
    jira : jira.Jira
        Jira object for Jira queries
    ids : list
        list of created Jira issue IDs
    """
    print("Deleting test Jira issues")
    for issue in issues:
        jira.delete_issue(issue['id'])


def simulate_end_to_end(day) -> None:
    """
    Run everything to test the checking of runs for deletion

    7 run states being simulated:

        - 1 run under ANSIBLE_WEEK weeks old (will be ignored)
        - 1 run old enough but no data uploaded (shouldn't happen)
        - 1 run run old enough and uploaded to stagingArea but no 002 project
        - 1 run old enough, uploaded and 002 project but ticket not in right state
        - 1 run that is old enough, uploaded, 002 project and ticket released
        - 1 run that failed sequencing and ticket at Data cannot be processed
        - 1 run that failed QC and ticket at Data cannot be released

    The last 3 of the above we expect to flag for deletion on a Monday
    and then delete on a Wednesday

    Parameters
    ----------
    day : int
        day of the week we're checking for
    """
    print("Simulating end to end running of checking and deletion")
    # below we will mock the function calls to dxpy to not need to create
    # a load of test projects, we're simulating 7 runs there will be
    # 7 returns for each patch

    # patch over logging in to DNAnexus
    patch('monitor.dx_login', return_value=True).start()

    # patch over the check for a run uploaded to StagingArea52
    patch(
        'monitor.check_run_uploaded',
        side_effect=[True, False, True, True, True, True, True]
    ).start()

    # patch over check of 002 project with minimal required describe details
    # n.b. for runs 2, 3 and 6 we are setting it to have no 002 project
    patch(
        'monitor.get_describe_data',
        side_effect=[
            {'describe': {'id': 'project-xxx'}},
            {},
            {},
            {'describe': {'id': 'project-xxx'}},
            {'describe': {'id': 'project-xxx'}},
            {},
            {'describe': {'id': 'project-xxx'}}
        ]
    ).start()

    # patch over datetime to simulate running on each day of the week,
    # since the day param starts at 1 and 04/03/2024 was a Monday, we
    # will add 3 to each iteration to start from Monday -> Sunday
    patch(
        'monitor.datetime',
        Mock(today=lambda: datetime(2024, 3, day + 3))
    ).start()

    # run end to end test including checking and deleting
    monitor.main()

    patch.stopall()


def main():
    print("Starting test run simulation...")

    if os.environ.get('HTTPS_PROXY'):
        # check if proxy set, if running locally and not on server this
        # will cause POST requests to time out
        print(
            f"NOTE: HTTPS proxy address set: {os.environ.get('HTTPS_PROXY')}"
        )

    jira = Jira(
        token=os.environ.get("JIRA_TOKEN"),
        email=os.environ.get("JIRA_EMAIL"),
        api_url=os.environ.get("JIRA_API_URL"),
        debug=True
    )

    # set up test data and Jira tickets
    create_run_suffix()
    delete_test_data()  # delete any old test data
    create_test_run_directories()
    create_test_logs()
    issues = create_jira_tickets(jira=jira)

    # simulate running the checking daily to check behaviour is correct
    for day in range(1, 8):
        print(f"\nStarting simulated check for {day_name[day - 1]}")
        try:
            simulate_end_to_end(jira=jira, day=day)
        except Exception:
            # ensure we always clean up test data
            print(f"Error occurred during checking")
            print(traceback.format_exc())

            delete_test_data()
            delete_jira_tickets(jira, issues)

            print("\nExiting now due to prior error")
            sys.exit()

    # pretty print to sense check the expected directories are deleted
    print("Final directory state after running for the week:")
    for sub_path in sorted(Path('simulate_test/').rglob('*')):
        print(f"\t{sub_path}")

    # clean up test data
    delete_test_data()
    delete_jira_tickets(jira, issues)


if __name__=="__main__":
    main()
