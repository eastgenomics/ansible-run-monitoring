import os
import sys
from datetime import datetime
import pandas as pd
import shutil

from bin.util import *
from bin.helper import get_logger
from bin.jira import Jira

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
    JIRA_URL = os.environ['JIRA_URL']
    JIRA_SLACK_URL = os.environ['SLACK_NOTIFY_JIRA_URL']

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
        exit()

    today = datetime.now()

    ansible_pickle = read_or_new_pickle(ANSIBLE_PICKLE)
    runs = ansible_pickle['runs']

    jira = Jira(JIRA_TOKEN, JIRA_EMAIL, JIRA_URL)

    if today.day == 1:
        deleted_runs = []
        for run, seq, status, key in runs:
            try:
                log.info(f'DELETING {run}')
                shutil.rmtree(f'{GENETIC_DIR}/{seq}/{run}')

                deleted_runs.append((run, seq, status, key))
            except OSError as err:
                log.error(err)
                clear_memory(ANSIBLE_PICKLE)

                log.info('END SCRIPT')
                sys.exit()

        post_message_to_slack(
            'egg-alerts',
            SLACK_TOKEN,
            deleted_runs,
            DEBUG,
            today=today,
            slack_url=JIRA_SLACK_URL,
            notification=True,
            delete=True
        )

    else:
        log.info(today)
        if runs:
            post_message_to_slack(
                'egg-logs',
                SLACK_TOKEN,
                runs,
                DEBUG,
                today=today,
                slack_url=JIRA_SLACK_URL,
                notification=True)
        else:
            log.info('NO RUNS IN MEMORY DETECTED')

        log.info('END SCRIPT')
        sys.exit()

    # get all sequencer in env
    seqs = [x for x in os.environ['ANSIBLE_SEQ'].split(',')]

    temp_pickle = []
    final_duplicates = []
    table_data = []

    genetic_directory, logs_directory, tmp_seq = get_runs(
        seqs, GENETIC_DIR, LOGS_DIR)

    # Get the duplicates between two directories /genetics & /var/log/
    temp_duplicates = set(genetic_directory) & set(logs_directory)

    log.info(f'Number of overlap files: {len(temp_duplicates)}')

    # for each project, we check if it exists on DNANexus
    for project in list(temp_duplicates):

        # check uploaded to staging52 project file (bool)
        uploaded_bool = check_project_directory(project, DNANEXUS_TOKEN)

        # check 002_ folder created
        proj_data = get_describe_data(project, DNANEXUS_TOKEN)

        assay, status, key = jira.get_issue_detail(project)

        if proj_data:
            # 002_ folder found

            data = proj_data['describe']
            old_enough, created_on, duration = check_age(
                data, today, ANSIBLE_WEEK)

            if old_enough:
                # folder is old enough = can be deleted

                if (
                        status.upper() == 'ALL SAMPLES RELEASED' and
                        assay in JIRA_ARRAY):
                    temp_pickle.append(
                        (project, tmp_seq[project], status, key))

                    log.info('{} {} ::: {} weeks PASS'.format(
                        project,
                        created_on,
                        duration.days / 7))

                    table_data.append(
                        (
                            project,
                            created_on,
                            '{} GB'.format(round(data['dataUsage'])),
                            data['createdBy']['user'],
                            round(duration.days / 7, 2),
                            True,
                            uploaded_bool,
                            True,
                            f'{assay}:{status}:True'
                        )
                    )

                    final_duplicates.append(project)

                    continue
                else:
                    log.info('{} {} ::: {} weeks FAILED JIRA - {}/{}'.format(
                        project,
                        created_on,
                        round(duration.days / 7, 2),
                        assay,
                        status))

                    table_data.append(
                        (
                            project,
                            created_on,
                            '{} GB'.format(round(data['dataUsage'])),
                            data['createdBy']['user'],
                            round(duration.days / 7, 2),
                            True,
                            uploaded_bool,
                            True,
                            f'{assay}:{status}:False'
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
                        '{} GB'.format(round(data['dataUsage'])),
                        data['createdBy']['user'],
                        round(duration.days / 7, 2),
                        False,
                        uploaded_bool,
                        True,
                        f'{assay}:{status}:False'
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
                    f'{assay}:{status}:False'
                )
            )

            log.info(f'NO DATA FOR: {project}')

            continue

    if not final_duplicates:
        log.info(f'No runs older than {ANSIBLE_WEEK} weeks')

        clear_memory(ANSIBLE_PICKLE)

        log.info('END SCRIPT')
        sys.exit()

    log.info(f'Number of old enough files: {len(final_duplicates)}')

    duplicates_dir = []

    # writing the directories path for each delete-able run
    for file in final_duplicates:
        fileseq = file.split('_')[1]
        duplicates_dir.append(f'/genetics/{fileseq}/{file}')

    # saving the directories into txt file (newline)
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
