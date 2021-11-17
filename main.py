import os
import sys
import datetime as dt
import pandas as pd
import dxpy as dx

from util import *
from helper import get_logger

log = get_logger("main log")


def main():

    dx_login()

    # Defining environment variables
    log.info('Fetching all environment variables')
    GENETIC_DIR = os.environ['ENV_GENETICDIR']
    LOGS_DIR = os.environ['ENV_LOGSDIR']

    sender = os.environ['ENV_SENDER']
    receivers = os.environ['ENV_RECEIVERS']
    receivers = receivers.split(',') if ',' in receivers else [receivers]

    seq = [x.upper() for x in os.environ['ENV_SEQ'].split(',')]

    duplicates = []
    final_duplicates = []
    table_data = []

    # Loop through each file in /genetics & /var/log/dx-stream-upload
    for file in seq:
        log.info('Loop through {} started'.format(file))
        gene_dir = '{}/{}'.format(GENETIC_DIR, file)
        logs_dir = '{}/{}'.format(LOGS_DIR, file)

        # Use set type to get duplicates
        gene_dir = set([x.strip() for x in os.listdir(gene_dir)])
        logs_dir = set([x.split('.')[1] for x in os.listdir(logs_dir)])

        log.info('Number of folders in /genetic: {} for seq {}'.format(
            len(gene_dir), file))
        log.info('Number of folders in /log: {} for seq {}'.format(
            len(logs_dir), file))

        # Get the duplicates between two directories /genetics & /var/log/
        temp_duplicates = gene_dir & logs_dir

        log.info('Number of overlap files: {}'.format(len(temp_duplicates)))

        duplicates += list(temp_duplicates)

    # find out if a run has been created for the project in dnanexus
    for project in duplicates:

        # check uploaded to staging52 project file (bool)
        uploaded_bool = check_project_directory(project)

        # check 002_ folder created
        describe = get_describe_data(project, sender, receivers)

        if describe:
            # 002_ folder found

            proj_des = describe['describe']

            today = dt.datetime.today()

            # convert millisec from Epoch datetime to readable human format
            created_date = dt.datetime.fromtimestamp(
                proj_des['created'] / 1000.0)
            created_on = created_date.strftime('%Y-%m-%d')

            duration = today - created_date

            # how many month old from env
            NUM_MONTH = os.environ['ENV_MONTH']

            # check if created_date is more than NUM_MONTH month(s)
            old_enough = duration.total_seconds() / (
                24*60*60) > 30 * int(NUM_MONTH)

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
                        duration.days,
                        uploaded_bool,
                        True,
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
                        duration.days,
                        uploaded_bool,
                        False,
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
                    'NO DATA',
                    uploaded_bool,
                    False,
                    False
                )
            )

            log.info('No return object from {}'.format(project))

    if not final_duplicates:
        log.info('No runs older than {} months'.format(NUM_MONTH))
        log.info('Program will stop here. There will be no email')
        sys.exit()

    log.info('Number of old enough files: {}'.format(len(final_duplicates)))

    duplicates_dir = []

    # create the directories path for each delete-able run
    for file in final_duplicates:
        fileseq = file.split('_')[1]
        duplicates_dir.append('/genetics/{}/{}'.format(fileseq, file))

    # saving the directories into txt file (newline)
    log.info('Writing text file')
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
            'Age',
            'Uploaded to Staging52',
            'Old Enough',
            '002 Directory Found'
            ]
        )

    # send the txt file (attachment) and dataframe as table in email
    send_mail(
        sender,
        receivers,
        'Ansible Run (Deletion)',
        df,
        ['duplicates.txt']
    )


if __name__ == "__main__":
    log.info('--------- Starting Script ----------')
    main()
    log.info('--------- End Script ----------')
