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
import json
import os
from pathlib import Path
import pickle
import shutil
import sys
import traceback
from unittest.mock import Mock, patch

from dateutil.relativedelta import relativedelta
from faker import Faker

from bin.jira import Jira
from bin.util import post_message_to_slack
import monitor


class SetUp():
    """
    Simple methods for setting up required test data structure
    """
    def __init__(self, jira):
        self.jira = jira
        self.issues = []
        self.suffix = None

        self.run_suffix()
        self.test_run_directories()
        self.test_logs()
        self.jira_tickets()


    def test_run_directories(self) -> None:
        """
        Create test run data structure of 7 runs, all but the first we're
        setting to be 'old enough' to delete (i.e. > ANSIBLE WEEKS old)
        """
        run_directories = [
            f"seq1/run1_{self.suffix}",
            f"seq1/run2_{self.suffix}",
            f"seq1/run3_{self.suffix}",
            f"seq1/run4_{self.suffix}",
            f"seq2/run5_{self.suffix}",
            f"seq2/run6_{self.suffix}",
            f"seq2/run7_{self.suffix}",
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


    def test_logs(self) -> None:
        """
        Create required log files as generated from dx-streaming-upload, these
        are used to checking if a directory is an monitored run directory
        that we have started at least uploading
        """
        os.makedirs("simulate_test/logs/seq1", exist_ok=True)
        os.makedirs("simulate_test/logs/seq2", exist_ok=True)

        for idx in range(0, 8):
            seq = 'seq1' if idx <5 else 'seq2'
            open(
                f"simulate_test/logs/{seq}/"
                f"run.run{idx}_{self.suffix}.lane.all.log", "w"
            ).close()


    def jira_tickets(self) -> list:
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
            f"run1_{self.suffix}": None,
            f"run2_{self.suffix}": None,
            f"run3_{self.suffix}": None,
            f"run4_{self.suffix}": None,
            f"run5_{self.suffix}": [31, 41, 21],  # Data released
            f"run6_{self.suffix}": [31, 61],      # Data cannot be processed
            f"run7_{self.suffix}": [31, 41, 71]   # Data cannot be released
        }

        created_issues = []

        for run, state in ticket_states.items():
            print(f"Creating Jira issue for {run}")
            issue = self.jira.create_issue(
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
                    self.jira.make_transition(
                        issue_id=issue['id'],
                        transition_id=transition
                    )

        self.issues = created_issues


    def run_suffix(self) -> None:
        """
        Generate random words to append to run ID to get a random name
        """
        self.suffix = '_'.join([Faker().word() for x in range(3)])


class CleanUp():
    """
    Simple methods for cleaning up test data

    Parameters
    ----------
    jira : jira.Jira
        Jira object for Jira queries
    ids : list
        list of created Jira issue IDs
    """
    def __init__(self, jira=None, issues=None):
        self.jira = jira
        self.issues = issues

        self.test_data()
        self.pickle()
        self.logging_log()
        self.recorded_deletion_log()
        self.jira_tickets()


    def test_data(self) -> None:
        """
        Check for test data directories and pickle file to clean up
        """
        print("Cleaning up test data directories")
        if os.path.exists('simulate_test'):
            shutil.rmtree('simulate_test')


    def pickle(self) -> None:
        """
        Delete the saved pickle file
        """
        if os.path.exists("check.pkl"):
            os.remove("check.pkl")


    def recorded_deletion_log(self) -> None:
        """
        Delete output log of deleted run directories
        """
        if os.path.exists("ansible_delete.txt"):
            os.remove("ansible_delete.txt")


    def logging_log(self) -> None:
        """
        Delete log file of stdout logging
        """
        return
        if os.path.exists("ansible-run-monitoring.log"):
            os.remove("ansible-run-monitoring.log")


    def jira_tickets(self) -> None:
        """
        Delete Jira issue tickets we created as part of testing
        """
        if self.jira and self.issues:
            print("Deleting test Jira issues")
            for issue in self.issues:
                self.jira.delete_issue(issue['id'])


class CheckBehaviour():
    """
    Check that the correct behaviour is observed for the given day of
    the week, the expected behaviour for each day is as follows:

    Monday -> 1 run identified as not old enough, 3 runs identified to
        delete and 3 identified for manual intervention, Slack alert
        sent and pickle file written to

    Tuesday -> same as above but no Slack alert and no pickling

    Wednesday -> same checks as above and runs deleted according to
        pickle file, pickle file then deleted

    Thursday-Sunday -> 1 run identified as not old enough, 3 identified
        for manual intervention, no Slack alert sent

    Parameters
    ----------
    day : int
        day of the week
    suffix : str
        randomly generated suffix string used for naming test directories
    slack_mock : mock.MagicMock
        Mock object for Slack notifications
    """
    def __init__(self, day, suffix, slack_mock):
        self.day = day
        self.suffix = suffix
        self.slack_mock = slack_mock

        self.errors = []
        self.runs_not_to_delete = [f"seq1/run{x}_{suffix}" for x in range(1, 5)]
        self.runs_to_delete = [f"seq2/run{x}_{suffix}" for x in range(5, 8)]

        if day == 1:
            self.check_monday()
        elif day == 2:
            self.check_tuesday()
        elif day == 3:
            self.check_wednesday()
        elif day in [4, 5, 6, 7]:
            self.check_thursday_to_sunday()
        else:
            # something has gone wrong
            print(f"Checking invalid day: {day}")


    def check_monday(self) -> None:
        """
        Check behaviour for running on Monday

        We expect to push 2 Slack notifications, update our pickle file
        with runs 5-7 to delete but not delete any directories
        """
        if self.slack_mock.call_count != 2:
            # we expect 2 calls to send Slack notifications
            self.errors.append(
                "Incorrect number of calls to Slack made: "
                f"{self.slack_mock.call_count}"
            )

        # TODO: check for contents of what is sent in Slack alert

        expected_pickle = (
            f"{os.environ.get('ANSIBLE_PICKLE_PATH')}/ansible_dict.test.pickle"
        )
        if not os.path.exists(expected_pickle):
            # check we have a pickle
            self.errors.append(
                "Pickle file of runs to delete not generated "
                f"at {expected_pickle}"
            )
        else:
            # check the pickle contains what we expect, keys will be the
            # run ID
            with open(expected_pickle, "rb") as f:
                pickle_contents = pickle.load(f)

            pickled_runs = sorted([
                x.split('_')[0] for x in pickle_contents.keys()
            ])

            if not pickled_runs == ['run5', 'run6', 'run7']:
                self.errors.append(
                    "Expected runs to delete not in pickle file, runs found: "
                    f"{pickle_contents.keys()}"
                )


    def check_tuesday(self) -> None:
        """
        Check behaviour for running on Tuesday

        We expect no Slack notifications, for the pickle file to be
        unmodified and for no deletion to take place
        """
        for run in self.runs_not_to_delete + self.runs_to_delete:
            # all run directories should still exist
            run_path = os.path.join(os.environ.get("ANSIBLE_GENETICDIR"), run)

            if not os.path.exists(run_path):
                self.errors.append(
                    f"Run directory wrongly deleted: {run_path}"
                )

        if self.slack_mock.call_count != 0:
            # we expect no calls to send Slack notifications
            self.errors.append("Slack notifications wrongly sent")


    def check_wednesday(self) -> None:
        """
        Check behaviour for running on Wednesday, we expect to delete the
        runs according to what was in the pickle file
        """
        for run in self.runs_not_to_delete:
            # check runs we *should not* have deleted
            run_path = os.path.join(os.environ.get("ANSIBLE_GENETICDIR"), run)
            if not os.path.exists(run_path):
                self.errors.append(
                    f"Run directory wrongly deleted: {run_path}"
                )

        for run in self.runs_to_delete:
            # check runs be *should* have deleted
            run_path = os.path.join(os.environ.get("ANSIBLE_GENETICDIR"), run)
            if os.path.exists(run_path):
                self.errors.append(
                    f"Run directory should have been deleted: {run_path}"
                )

        if self.slack_mock.call_count != 0:
            # we expect no calls to send Slack notifications
            self.errors.append("Slack notifications wrongly sent")


    def check_thursday_to_sunday(self) -> None:
        """
        Check behaviour for running on Thursday - Sunday

        We should not be deleting anything, sending no Slack notifications
        and the pickle file should be unmodified
        """
        for run in self.runs_not_to_delete:
            # everything should still exist
            run_path = os.path.join(os.environ.get("ANSIBLE_GENETICDIR"), run)
            if not os.path.exists(run_path):
                self.errors.append(
                    f"Run directory wrongly deleted: {run_path}"
                )

        if self.slack_mock.call_count != 0:
            # we expect no calls to send Slack notifications
            self.errors.append("Slack notifications wrongly sent")


def simulate_end_to_end(day, suffix) -> list:
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
    suffix : str
        randomly generated suffix string used for naming test directories

    Returns
    -------
    list
        list of any encountered errors
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

    # mock the function that sends notifications to Slack to check for
    # how many times it is called without stopping the actual requests
    # slack_mock = Mock(side_effect=post_simple_message_to_slack)
    # slack_mock()
    slack_mock = patch(
        'monitor.post_message_to_slack',
        wraps=monitor.post_message_to_slack
    )
    slack_mock = slack_mock.start()

    # run end to end test including checking and deleting
    monitor.main()

    # check our behaviour is correct and build summary
    checks = CheckBehaviour(
        day=day,
        suffix=suffix,
        slack_mock=slack_mock
    )

    patch.stopall()

    return checks.errors


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

    # delete any old test data
    CleanUp()

    # set up test data and Jira tickets
    test_data = SetUp(jira=jira)

    errors = {}

    # simulate running the checking daily to check behaviour is correct
    for day in range(1, 8):
        print(f"\nStarting simulated check for {day_name[day - 1]}")
        try:
            daily_errors = simulate_end_to_end(
                day=day,
                suffix=test_data.suffix
            )
            errors[day_name[day -1]] = daily_errors
        except Exception:
            # ensure we always clean up test data
            print(f"Error occurred during checking")
            print(traceback.format_exc())

            CleanUp(jira=jira, issues=test_data.issues)

            print("\nExiting now due to prior error")
            sys.exit()

    # pretty print to sense check the expected directories are deleted
    print("Final directory state after running for the week:")
    for sub_path in sorted(Path('simulate_test/').rglob('*')):
        print(f"\t{sub_path}")

    # clean up test data
    CleanUp(jira=jira, issues=test_data.issues)

    if any(errors.values()):
        # one or more checks did not pass
        print(f"\nOne or more errors occurred from daily checks")
        for day, error in errors.items():
            if error:
                print(f"{day}:", json.dumps(error, indent='  '))
    else:
        print("\nDaily checking worked as expected, no errors detected")


if __name__=="__main__":
    main()
