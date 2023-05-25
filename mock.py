# Mock test script
"""
Script will create run directory for run in test/runs.txt
Log file for each created run will be created in /log/dx-streaming/upload
three type of outcome will be produced
1. run with samples not yet released (> 30 days)
2. run without jira ticket (> 1 or 2 day)
3. run qualified for deletion

Edit your local datetime to simulate the script running on different date
1st should delete runs in memory (if there is)
24th should trigger sending alert to Slack (if there is runs in memory)

Every run will check for stale run

"""
import os
import random
import string
import datetime as dt
from dateutil.relativedelta import relativedelta
import shutil
import time
import argparse
import pickle
import collections

from bin.jira import Jira

JIRA_TOKEN = os.environ["JIRA_TOKEN"]
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_URL = os.environ["JIRA_API_URL"]
ANSIBLE_WEEK = int(os.environ["ANSIBLE_WEEK"]) + 1
DEBUG = os.environ["ANSIBLE_DEBUG"]
SEQUENCERS = [seq.strip() for seq in os.environ["ANSIBLE_SEQ"].split(",")]

os.environ["PYTHONUNBUFFERED"] = "1"

stale_runs = []
delete_runs = []


def get_random_string(length: int):
    """
    Function to create random string of variable length
    """
    letters = string.ascii_lowercase
    result_str = "".join(random.choice(letters) for i in range(length))
    return result_str


def list_files(startpath):
    """
    Function to pretty print directories
    """
    for root, _, files in os.walk(startpath):
        level = root.replace(startpath, "").count(os.sep)
        indent = " " * 4 * (level)
        print("{}{}/".format(indent, os.path.basename(root)))
        subindent = " " * 4 * (level + 1)
        for f in files:
            print("{}{}".format(subindent, f))


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


parser = argparse.ArgumentParser(description="additional functions")
parser.add_argument(
    "-c",
    "--clear",
    action="store_true",
    help="clear all directories in /genetics",
)
args = parser.parse_args()


jira = Jira(JIRA_TOKEN, JIRA_EMAIL, JIRA_API_URL, DEBUG)

today = dt.datetime.today()

# set modified date of mock directories to be old enough
stale_date = today + relativedelta(days=-2)
old_date = today + relativedelta(weeks=-ANSIBLE_WEEK)
old_epoch = old_date.timestamp()
stale_epoch = stale_date.timestamp()

print(stale_date, old_date)

with open("/home/test/runs.txt") as f:
    lines = f.readlines()
    lines = [line.rstrip("\n") for line in lines]


memory = read_or_new_pickle("/log/monitoring/ansible_dict.test.pickle")
if memory:
    print("memory detected in pickle file")
    print("/test/log/monitoring/ansible_dict.test.pickle")
    print("skipping mock.py and running main.py")
    lines = []

for seq in SEQUENCERS:
    print(f"Creating /log/dx-streaming-upload/{seq}")
    os.makedirs(f"/log/dx-streaming-upload/{seq}", exist_ok=True)


seq = "A01295a"

if args.clear:
    print("Deleting all directories in /genetics")
    for run in os.listdir(f"/genetics/{seq}"):
        if run == ".gitignore":
            continue
        try:
            shutil.rmtree(f"/genetics/{seq}/{run}")
        except Exception as e:
            print(e)
            continue

delete_count = 0
stale_count = 0

for run in lines:
    print(f"Creating {run}")
    # delete existing runs in directory
    if os.path.isdir(f"/genetics/{seq}/{run}"):
        shutil.rmtree(f"/genetics/{seq}/{run}")

    os.makedirs(f"/genetics/{seq}/{run}", exist_ok=True)

    # make it a nested directory
    os.makedirs(f"/genetics/{seq}/{run}/nested", exist_ok=True)

    # generate file within the directory, varying filesize
    with open(f"/genetics/{seq}/{run}/{get_random_string(5)}.txt", "w") as f:
        d = 3
        n = random.randint(10000, 550000)
        for i in range(n):
            nums = [str(round(random.uniform(0, 1000), 3)) for j in range(d)]
            f.write(" ".join(nums))
            f.write("\n")
        f.write("This is a content file")

    with open(f"/genetics/{seq}/{run}/nested/run.{run}.all.log", "w") as f:
        f.write("This is just a random file in a nested directory")

    issues = jira.search_issue(run, project_name="EBHD")
    total = issues["total"]

    if total != 0:
        # if there is already created issue, delete them
        print(f"Deleting jira ticket: {run}")
        if total > 1:
            for issue in issues["issues"]:
                id = issue["id"]
                jira.delete_issue(id)
        else:
            jira.delete_issue(issues["issues"][0]["id"])

    option = random.choice([1, 2, 3])

    # this does not guarantee that a 002 project is on DNANexus
    # randomly, we generate either stale Jira ticket or PASS ticket
    if option == 1:
        # stale run
        # created date > 30 and still not yet sample released

        # change modified time
        os.utime(f"/genetics/{seq}/{run}", (old_epoch, old_epoch))

        issue = jira.create_issue(
            run,
            10179,  # issue type
            10042,  # EBHD id
            "61703e0925f313007059993f",
            3,
            "",
            True,
        )

        stale_runs.append(f"{run} -> not yet released")
        stale_count += 1

    elif option == 2:
        # stale run
        # created date > 1 and no Jira ticket

        # change modified time
        os.utime(f"/genetics/{seq}/{run}", (stale_epoch, stale_epoch))

        stale_runs.append(f"{run} -> no associated jira ticket")
        stale_count += 1
    else:
        # old enough
        # jira ticket all samples released

        # change modified time
        os.utime(f"/genetics/{seq}/{run}", (old_epoch, old_epoch))

        issue = jira.create_issue(
            run,
            10179,  # issue type
            10042,  # EBHD id
            "61703e0925f313007059993f",
            3,
            "",
            True,
        )
        id = issue["id"]

        for transition_id in [31, 41, 21]:
            jira.make_transition(id, transition_id)
            time.sleep(3)

        delete_count += 1

        delete_runs.append(f"{run} -> pass")

print(f"Runs marked for deletion: {delete_count}")
print(f"Runs marked as stale: {stale_count}")

# make run log file in /log
for d in os.listdir(f"/genetics/{seq}"):
    if d == ".gitignore":
        continue
    with open(
        f"/log/dx-streaming-upload/{seq}/run.{d}.lane.all.log", "w"
    ) as f:
        f.write("This is a log file")

# generate a report txt to show mock run sample that PASS and fit the criteria
# for deletion in the next run
with open(f"/log/monitoring/{today}-report.txt", "a") as f:
    f.write(f"today: {today}\n")
    f.write(f"stale cutt-off: {stale_date}\n")
    f.write(f"old enough cut-off: {old_date}\n")

    for row in sorted(stale_runs):
        f.write(f"{row}\n")

    f.write("\n")

    for row in sorted(delete_runs):
        f.write(f"{row}\n")

    f.write("\n")

    f.write("**run the script with datetime set to 1st of any month\n")
    f.write("we should expect those runs above that PASS be deleted\n")
    f.write("and acknowledgement Jira ticket should show up on EBHD\n")
