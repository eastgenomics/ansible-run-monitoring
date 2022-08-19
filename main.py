import os
import sys
from datetime import datetime
import pandas as pd
import shutil

from util import *
from helper import get_logger
from jira import Jira

log = get_logger("main log")


def main():

    GENETIC_DIR = os.environ['ANSIBLE_GENETICDIR']
    LOGS_DIR = os.environ['ANSIBLE_LOGSDIR']
    ANSIBLE_WEEK = int(os.environ['ANSIBLE_WEEK'])
    ANSIBLE_PICKLE = os.environ['ANSIBLE_PICKLE_PATH']

    SERVER = os.environ['ANSIBLE_SERVER']
    PORT = int(os.environ['ANSIBLE_PORT'])

    SENDER = os.environ['ANSIBLE_SENDER']
    receivers = os.environ['ANSIBLE_RECEIVERS']
    receivers = receivers.split(',') if ',' in receivers else [receivers]

    DEBUG = os.environ.get('ANSIBLE_DEBUG', False)

    DNANEXUS_TOKEN = os.environ["DNANEXUS_TOKEN"]
    SLACK_TOKEN = os.environ['SLACK_TOKEN']

    JIRA_TOKEN = os.environ['JIRA_TOKEN']
    JIRA_EMAIL = os.environ['JIRA_EMAIL']
    JIRA_ARRAY = [
        array for array in os.environ['ANSIBLE_JIRA_ARRAY'].split(',')]

    if DEBUG:
        log.info('Running in DEBUG mode')
    else:
        log.info('Running in PRODUCTION mode')

    if not dx_login(DNANEXUS_TOKEN):
        message = "ANSIBLE-MONITORING: ERROR with dxpy login!"

        post_message_to_slack('egg-alerts', SLACK_TOKEN, message, DEBUG)
        log.info('END SCRIPT')
        sys.exit()

    if not directory_check([GENETIC_DIR, LOGS_DIR]):
        message = f"ANSIBLE-MONITORING: ERROR with missing directory"

        post_message_to_slack('egg-alerts', SLACK_TOKEN, message, DEBUG)
        log.info('END SCRIPT')
        sys.exit()

    today = datetime.now()

    ansible_pickle = read_or_new_pickle(ANSIBLE_PICKLE)
    runs = ansible_pickle['runs']

    jira = Jira(JIRA_TOKEN, JIRA_EMAIL)

    if today.day == 1:
        for run, seq, _, _ in runs:
            try:
                if not DEBUG:
                    log.info(f'DELETING {run}')
                    shutil.rmtree(f'{GENETIC_DIR}/{seq}/{run}')
                else:
                    log.info('DEBUG: DELETE RUNS...')
            except OSError as err:
                log.error(err)
                log.info('END SCRIPT')
                sys.exit()
    else:
        log.info(today)
        if runs:
            post_message_to_slack(
                'egg-logs',
                SLACK_TOKEN,
                runs,
                DEBUG,
                today,
                True)
        else:
            log.info('NO RUNS DETECTED')

        log.info('END SCRIPT')
        sys.exit()

    # get all sequencer in env
    seqs = [x for x in os.environ['ANSIBLE_SEQ'].split(',')]

    temp_pickle = []
    temp_sequencer = {}
    final_duplicates = []
    table_data = []

    genetic_directory = []
    logs_directory = []

    for sequencer in seqs:
        log.info(f'Loop through {sequencer} started')

        # Defining gene and log directories
        gene_dir = f'{GENETIC_DIR}/{sequencer}'
        logs_dir = f'{LOGS_DIR}/{sequencer}'

        # Get all files in gene and log dir
        genetic_files = [x.strip() for x in os.listdir(gene_dir)]
        genetic_directory += genetic_files
        logs_directory += [
            x.split('.')[1].strip() for x in os.listdir(logs_dir)]

        for run in genetic_files:
            temp_sequencer[run] = sequencer

        genetics_num = len(os.listdir(gene_dir))
        logs_num = len(os.listdir(logs_dir))

        log.info(f'{genetics_num} folders in {sequencer} detected')
        log.info(f'{logs_num} logs in {sequencer} detected')

    # Get the duplicates between two directories /genetics & /var/log/
    temp_duplicates = set(genetic_directory) & set(logs_directory)

    log.info(f'Number of overlap files: {len(temp_duplicates)}')

    # for each project, we check if it exists on DNANexus
    for project in list(temp_duplicates):

        # check uploaded to staging52 project file (bool)
        uploaded_bool = check_project_directory(project)

        # check 002_ folder created
        proj_data = get_describe_data(project)

        array, status, key = jira.get_issue_detail(project)

        if proj_data:
            # 002_ folder found

            proj_des = proj_data['describe']

            # convert millisec from Epoch datetime to readable human format
            created_date = datetime.fromtimestamp(
                proj_des['created'] / 1000.0)
            created_on = created_date.strftime('%Y-%m-%d')

            duration = today - created_date

            # check if created_date is more than ANSIBLE_WEEK week(s)
            # duration (sec) / 60 to minute / 60 to hour / 24 to days
            # If total days is > 7 days * 6 weeks
            old_enough = duration.total_seconds() / (
                24*60*60) > 7 * int(ANSIBLE_WEEK)

            if old_enough:
                # folder is old enough = can be deleted

                if (
                        status.upper() == 'ALL SAMPLES RELEASED' and
                        array in JIRA_ARRAY):
                    temp_pickle.append(
                        (project, temp_sequencer[project], status, key))

                    log.info('{} {} ::: {} weeks PASS'.format(
                        project,
                        created_on,
                        duration.days / 7))

                    table_data.append(
                        (
                            project,
                            created_on,
                            '{} GB'.format(round(proj_des['dataUsage'])),
                            proj_des['createdBy']['user'],
                            round(duration.days / 7, 2),
                            True,
                            uploaded_bool,
                            True,
                            f'{array}:{status}:True'
                        )
                    )

                    continue
                else:
                    log.info('{} {} ::: {} weeks FAILED JIRA - {}/{}'.format(
                        project,
                        created_on,
                        round(duration.days / 7, 2),
                        array,
                        status))

                    table_data.append(
                        (
                            project,
                            created_on,
                            '{} GB'.format(round(proj_des['dataUsage'])),
                            proj_des['createdBy']['user'],
                            round(duration.days / 7, 2),
                            True,
                            uploaded_bool,
                            True,
                            f'{array}:{status}:False'
                        )
                    )

                    final_duplicates.append(project)

                    continue

            else:
                # folder is not old enough

                log.info('{} {} ::: {} weeks REJECTED'.format(
                    project,
                    created_on,
                    round(duration.days / 7, 2)))

                table_data.append(
                    (
                        project,
                        created_on,
                        '{} GB'.format(round(proj_des['dataUsage'])),
                        proj_des['createdBy']['user'],
                        round(duration.days / 7, 2),
                        False,
                        uploaded_bool,
                        True,
                        f'{array}:{status}:False'
                    )
                )

                continue

        else:
            # 002_ folder NOT found

            table_data.append(
                (
                    project,
                    None,
                    None,
                    None,
                    None,
                    False,
                    uploaded_bool,
                    False,
                    f'{array}:{status}:False'
                )
            )

            log.info(f'NO DATA FOR: {project}')

            continue

    if not final_duplicates:
        log.info(f'No runs older than {ANSIBLE_WEEK} weeks')
        log.info('END SCRIPT')
        sys.exit()

    log.info(f'Number of old enough files: {len(final_duplicates)}')

    duplicates_dir = []

    # writing the directories path for each delete-able run
    for file in final_duplicates:
        fileseq = file.split('_')[1]
        duplicates_dir.append(f'/genetics/{fileseq}/{file}')

    # saving the directories into txt file (newline)
    if not DEBUG:
        log.info('Writing to text file')
        with open('duplicates.txt', 'w') as f:
            f.write('\n'.join(duplicates_dir))

    # dataframe creation for all runs describe=True data
    df = pd.DataFrame(
        table_data,
        columns=[
            'Project Name',
            'Created',
            'Data Usage',
            'Created By',
            'Age (Weeks)',
            'Old Enough',
            'Present in Staging52',
            '002 Project Found',
            'Array:Jira Status:Delete'
            ]
        )

    df = df.sort_values(
        by='Age (Weeks)', ascending=False).reset_index(drop=True)

    # send the txt file (attachment) and dataframe as table in email
    if not DEBUG:
        send_mail(
            SENDER,
            receivers,
            'Ansible Run (Deletion)',
            SERVER,
            PORT,
            df=df,
            files=['duplicates.txt']
        )

    # save memory dict (in PROD only)
    ansible_pickle['runs'] = temp_pickle

    log.info('Writing into pickle file')
    with open(ANSIBLE_PICKLE, 'wb') as f:
        pickle.dump(ansible_pickle, f)


if __name__ == "__main__":
    log.info('STARTING SCRIPT')
    main()
    log.info('END SCRIPT')
