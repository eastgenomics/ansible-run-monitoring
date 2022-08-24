import os
import random
import string

from bin.jira import Jira

JIRA_TOKEN = os.environ['JIRA_TOKEN']
JIRA_EMAIL = os.environ['JIRA_EMAIL']
JIRA_URL = os.environ['JIRA_URL']

os.environ['PYTHONUNBUFFERED'] = '1'

jira = Jira(JIRA_TOKEN, JIRA_EMAIL, JIRA_URL)

with open('/home/test/runs.txt') as f:
    lines = f.readlines()
    lines = [line.rstrip('\n') for line in lines]

run = random.choice(lines)


def get_random_string(length: int):
    """
    Function to create random string of variable length
    """
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


seq = 'A01295a'

print(f'Creating the run directory ({run}) in /genetics')
os.makedirs(f'/genetics/{seq}/{run}', exist_ok=True)

# make run log file in /log
for d in os.listdir(f'/genetics/{seq}'):
    with open(
            f'/log/dx-streaming-upload/{seq}/run.{d}.lane.all.log', 'w') as f:
        f.write('This is a log file')

# make it a nested directory
os.makedirs(f'/genetics/{seq}/{run}/nested', exist_ok=True)

with open(f'/genetics/{seq}/{run}/{get_random_string(5)}.txt', 'w') as f:
    f.write('This is a content file')

with open(f'/genetics/{seq}/{run}/nested/run.{run}.lane.all.log', 'w') as f:
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
