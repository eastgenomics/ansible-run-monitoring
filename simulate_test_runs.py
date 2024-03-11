"""
Outline of end to end test to set up

Runs with the following:
    - 1 run under X weeks old
        - these should be logged as not old enough and excluded
    - Runs criteria that should be logged as error and flagged for manual review
        - 1 run old enough but no data uploaded (shouldn't happen)
        - 1 run run old enough and uploaded to stagingArea but no 002 project
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
from datetime import datetime
from faker import Faker
import os
import shutil
from unittest.mock import Mock, patch
from dateutil.relativedelta import relativedelta

from bin.jira import Jira
from main import check_for_deletion, delete_runs


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

    open(f"simulate_test/logs/seq1/run.run1_{SUFFIX}.lane.all.log", "w").close()
    open(f"simulate_test/logs/seq1/run.run2_{SUFFIX}.lane.all.log", "w").close()
    open(f"simulate_test/logs/seq1/run.run3_{SUFFIX}.lane.all.log", "w").close()
    open(f"simulate_test/logs/seq2/run.run4_{SUFFIX}.lane.all.log", "w").close()
    open(f"simulate_test/logs/seq2/run.run5_{SUFFIX}.lane.all.log", "w").close()
    open(f"simulate_test/logs/seq2/run.run6_{SUFFIX}.lane.all.log", "w").close()
    open(f"simulate_test/logs/seq2/run.run7_{SUFFIX}.lane.all.log", "w").close()


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
    Generate a random word to append to run ID to get a random name,
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
    print("Deleting test data directories")
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


def simulate_checking(jira, day) -> None:
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

    The last 3 of the above we expect to flag for deletion

    Parameters
    ----------
    jira : jira.Jira
        Jira object for Jira queries
    day : int
        day of the week we're checking for
    """
    print("Simulating checking of run directories")
    # things we need to mock to not actually call external resources, since
    # we're simulating 7 runs there will be 7 returns for each patch

    # patch over the check for a run uploaded to StagingArea52
    patch(
        'main.check_run_uploaded',
        side_effect=[True, False, True, True, True, True, True]
    ).start()

    # patch over check of 002 project with minimal required describe details
    patch(
        'main.get_describe_data',
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
    # will add 3 for each iteration
    patch(
        'main.datetime',
        Mock(today=lambda: datetime(2024, 3, day + 3))
    ).start()

    check_for_deletion(
        seqs=["seq1", "seq2"],
        genetics_dir="simulate_test",
        logs_dir="simulate_test/logs",
        ansible_week=2,
        server_testing=False,
        slack_token=os.environ.get("SLACK_TOKEN"),
        pickle_file="check.pkl",
        debug=True,
        jira_assay=["MYE", "CEN", "TWE"],
        jira_url=os.environ.get("SLACK_NOTIFY_JIRA_URL"),
        jira=jira
    )

    patch.stopall()


def simulate_deletion(jira) -> None:
    """
    Simulate running on a Wednesday and deleting runs according to what
    is stored in the pickle file

    Parameters
    ----------
    jira : jira.Jira
        Jira object for Jira queries
    """
    print("Simulating deletion of run directories")

    delete_runs(
        pickle_file="check.pkl",
        genetics_dir="simulate_test/",
        jira_project_id=env.jira_project_id,
        jira_reporter_id=env.jira_reporter_id,
        slack_token=env.slack_token,
        server_testing=env.server_testing,
        debug=env.debug,
        jira=jira
    )


def main():
    print("Starting test run simulation...")

    if os.environ.get('HTTPS_PROXY'):
        # check if proxy set, if running locally and not on server this
        # will cause POST requests to time out
        print(
            f"Note: HTTPS proxy address set: {os.environ.get('HTTPS_PROXY')}"
        )

    jira = Jira(
        token=os.environ.get("JIRA_TOKEN"),
        email=os.environ.get("JIRA_EMAIL"),
        api_url=os.environ.get("JIRA_API_URL"),
        debug=True
    )

    # simulate running the checking daily to check behaviour is correct
    for day in range(1, 8):
        # set up test data and Jira tickets
        create_run_suffix()
        delete_test_data()  # delete any old test data
        create_test_run_directories()
        create_test_logs()
        issues = create_jira_tickets(jira=jira)

        stop = False

        try:
            simulate_checking(jira=jira, day=day)
        except Exception as err:
            # ensure we always clean up test data
            print(f"Error occured during checking: {err}")
            stop = True

        # clean up test data
        delete_test_data()
        delete_jira_tickets(jira, issues)

        if stop:
            print("Exiting now due to prior error")

    # simulate_deletion(jira=jira)


if __name__=="__main__":
    main()
