import os
import sys
import datetime as dt
import pandas as pd

from util import *
from helper import get_logger

log = get_logger("main log")


def main():

    GENETIC_DIR = os.environ['ANSIBLE_GENETICDIR']
    LOGS_DIR = os.environ['ANSIBLE_LOGSDIR']
    NUM_WEEK = os.environ['ANSIBLE_WEEK']

    SERVER = os.environ['ANSIBLE_SERVER']
    PORT = int(os.environ['ANSIBLE_PORT'])

    SENDER = os.environ['ANSIBLE_SENDER']
    receivers = os.environ['ANSIBLE_RECEIVERS']
    receivers = receivers.split(',') if ',' in receivers else [receivers]

    DEBUG = os.environ.get('ANSIBLE_DEBUG', False)
    DNANEXUS_TOKEN = os.environ["DNANEXUS_TOKEN"]

    if DEBUG:
        log.info('Running in DEBUG mode')
    else:
        log.info('Running in PRODUCTION mode')

    if dx_login(DNANEXUS_TOKEN):
        pass
    else:
        message = "ANSIBLE-MONITORING: ERROR with dxpy login!"
        post_message_to_slack('egg-alerts', message, DEBUG)
        log.info('END SCRIPT')
        sys.exit()

    if directory_check([GENETIC_DIR, LOGS_DIR]):
        pass
    else:
        message = f"ANSIBLE-MONITORING: ERROR with missing directory"

        post_message_to_slack('egg-alerts', message, DEBUG)
        log.info('END SCRIPT')
        sys.exit()

    today = dt.datetime.today()

    # get all sequencer in env
    seqs = [x.upper() for x in os.environ['ANSIBLE_SEQ'].split(',')]

    duplicates = []
    final_duplicates = []
    table_data = []

    for sequencer in seqs:
        log.info(f'Loop through {sequencer} started')

        # Defining gene and log directories
        gene_dir = f'{GENETIC_DIR}/{sequencer}'
        logs_dir = f'{LOGS_DIR}/{sequencer}'

        # Get all files in gene and log dir
        gene_dir = set([x.strip() for x in os.listdir(gene_dir)])
        logs_dir = set([x.split('.')[1].strip() for x in os.listdir(logs_dir)])

        log.info(
            f'Number of folders in genetic: {len(gene_dir)} for {sequencer}')
        log.info(
            f'Number of folders in log: {len(logs_dir)} for {sequencer}')

        # Get the duplicates between two directories /genetics & /var/log/
        temp_duplicates = gene_dir & logs_dir

        log.info(f'Number of overlap files: {len(temp_duplicates)}')

        duplicates += list(temp_duplicates)

    # for each project, we check if it exists on DNANexus
    for project in duplicates:

        # check uploaded to staging52 project file (bool)
        uploaded_bool = check_project_directory(project)

        # check 002_ folder created
        proj_data = get_describe_data(project)

        if proj_data:
            # 002_ folder found

            proj_des = proj_data['describe']

            # convert millisec from Epoch datetime to readable human format
            created_date = dt.datetime.fromtimestamp(
                proj_des['created'] / 1000.0)
            created_on = created_date.strftime('%Y-%m-%d')

            duration = today - created_date

            # check if created_date is more than NUM_WEEK week(s)
            # duration (sec) / 60 to minute / 60 to hour / 24 to days
            # If total days is > 7 days * 6 weeks
            old_enough = duration.total_seconds() / (
                24*60*60) > 7 * int(NUM_WEEK)

            if old_enough:
                # folder is old enough = can be deleted

                log.info('{} {} ::: {} days PASS'.format(
                    project,
                    created_on,
                    duration.days))

                table_data.append(
                    (
                        project,
                        created_on,
                        '{} GB'.format(round(proj_des['dataUsage'])),
                        proj_des['createdBy']['user'],
                        round(duration.days / 7, 2),
                        True,
                        uploaded_bool,
                        True
                    )
                )

                final_duplicates.append(project)

                continue

            else:
                # folder is not old enough

                log.info('{} {} ::: {} days REJECTED'.format(
                    project,
                    created_on,
                    duration.days))

                table_data.append(
                    (
                        project,
                        created_on,
                        '{} GB'.format(round(proj_des['dataUsage'])),
                        proj_des['createdBy']['user'],
                        round(duration.days / 7, 2),
                        False,
                        uploaded_bool,
                        True
                    )
                )

                continue

        else:
            # 002_ folder NOT found

            table_data.append(
                (
                    project,
                    'NO DATA',
                    'NO DATA',
                    'NO DATA',
                    None,
                    False,
                    uploaded_bool,
                    False
                )
            )

            log.info(f'No proj describe data for: {project}')

            continue

    if not final_duplicates:
        log.info(f'No runs older than {NUM_WEEK} weeks')
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
            'Uploaded to Staging52',
            '002 Directory Found'
            ]
        )

    df = df.sort_values(by='Age (Weeks)', ascending=False).reset_index()

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


if __name__ == "__main__":
    log.info('STARTING SCRIPT')
    main()
    log.info('END SCRIPT')
