import os
import random
import string
import datetime as dt
from dateutil.relativedelta import relativedelta
from itertools import cycle
import shutil

from bin.jira import Jira

JIRA_TOKEN = os.environ['JIRA_TOKEN']
JIRA_EMAIL = os.environ['JIRA_EMAIL']
JIRA_API_URL = os.environ['JIRA_API_URL']
ANSIBLE_WEEK = int(os.environ['ANSIBLE_WEEK']) + 1
DEBUG = os.environ['ANSIBLE_DEBUG']

os.environ['PYTHONUNBUFFERED'] = '1'

jira = Jira(JIRA_TOKEN, JIRA_EMAIL, JIRA_API_URL, DEBUG)

today = dt.datetime.today()

# set modified date of mock directories to be old enough
target_date = today + relativedelta(weeks=-ANSIBLE_WEEK)

iterator = cycle([today, target_date])
print(f'Today: {today}')
print(f'Mock Date: {target_date}')

with open('/home/test/runs.txt') as f:
    lines = f.readlines()
    lines = [line.rstrip('\n') for line in lines]


def get_random_string(length: int):
    """
    Function to create random string of variable length
    """
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


# run = random.choice(lines)
seq = 'A01295a'

for run in lines:
    # delete existing runs
    if os.path.isdir(f'/genetics/{seq}/{run}'):
        shutil.rmtree(f'/genetics/{seq}/{run}')

    print(f'Creating the run directory ({run}) in /genetics')
    os.makedirs(f'/genetics/{seq}/{run}', exist_ok=True)

    # make it a nested directory
    os.makedirs(f'/genetics/{seq}/{run}/nested', exist_ok=True)

    print('Generating a large file within it.')
    with open(f'/genetics/{seq}/{run}/{get_random_string(5)}.txt', 'w') as f:
        d = 3
        n = random.randint(10000, 550000)
        for i in range(n):
            nums = [str(round(random.uniform(0, 1000), 3)) for j in range(d)]
            f.write(' '.join(nums))
            f.write('\n')
        f.write('This is a content file')

    with open(f'/genetics/{seq}/{run}/nested/run.{run}.all.log', 'w') as f:
        f.write('This is just a random file in nested directory')

    # epoch time
    date = next(iterator).timestamp()

    os.utime(f'/genetics/{seq}/{run}', (date, date))

# make run log file in /log
for d in os.listdir(f'/genetics/{seq}'):
    with open(
            f'/log/dx-streaming-upload/{seq}/run.{d}.lane.all.log', 'w') as f:
        f.write('This is a log file')


def list_files(startpath):
    """
    Function to pretty print directories
    """
    for root, _, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print('{}{}/'.format(indent, os.path.basename(root)))
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print('{}{}'.format(subindent, f))


print('=== GENETICS DIRECTORY ===')
list_files('/genetics')

print('=== LOG DIRECTORY ===')
list_files('/log')


