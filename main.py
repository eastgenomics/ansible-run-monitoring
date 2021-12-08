import os
import sys
import datetime as dt
import pandas as pd
import dxpy as dx

from util import *
from helper import get_logger

log = get_logger("main log")


def main():

    GENETIC_DIR = os.environ['ANSIBLE_GENETICDIR']
    LOGS_DIR = os.environ['ANSIBLE_LOGSDIR']
    NUM_MONTH = os.environ['ANSIBLE_MONTH']

    sender = os.environ['ANSIBLE_SENDER']
    receivers = os.environ['ANSIBLE_RECEIVERS']
    receivers = receivers.split(',') if ',' in receivers else [receivers]

    dx_login(sender, receivers)
    dir_check([GENETIC_DIR, LOGS_DIR])

    seq = [x.upper() for x in os.environ['ANSIBLE_SEQ'].split(',')]

    duplicates = []
    final_duplicates = []
    table_data = []

    # Loop through each file in /genetics & /var/log/dx-stream-upload
    for file in seq:
        log.info('Loop through {} started'.format(file))
        gene_dir = f'{GENETIC_DIR}/{file}'
        logs_dir = f'{LOGS_DIR}/{file}'

        # Use set type to get duplicates
        gene_dir = set([x.strip() for x in os.listdir(gene_dir)])
        logs_dir = set([x.split('.')[1] for x in os.listdir(logs_dir)])

        log.info('Number of folders in /genetic: {} for seq {}'.format(
            len(gene_dir), file))
        log.info('Number of folders in /log: {} for seq {}'.format(
            len(logs_dir), file))

        # Get the duplicates between two directories /genetics & /var/log/
        temp_duplicates = gene_dir & logs_dir

        log.info(f'Number of overlap files: {len(temp_duplicates)}')

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
                        duration.days,
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
                    0,
                    False,
                    uploaded_bool,
                    False
                )
            )

            log.info(f'No return object from {project}')

    if not final_duplicates:
        log.info(f'No runs older than {NUM_MONTH} months')
        log.info('Program will stop here. There will be no email')
        sys.exit()

    log.info(f'Number of old enough files: {len(final_duplicates)}')

    duplicates_dir = []

    # create the directories path for each delete-able run
    for file in final_duplicates:
        fileseq = file.split('_')[1]
        duplicates_dir.append(f'/genetics/{fileseq}/{file}')

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
            'Old Enough',
            'Uploaded to Staging52',
            '002 Directory Found'
            ]
        )

    df = df.sort_values(by='Age', ascending=False)

    # send the txt file (attachment) and dataframe as table in email
    send_mail(
        sender,
        receivers,
        'Ansible Run (Deletion)',
        df,
        ['duplicates.txt']
    )


if __name__ == "__main__":
    log.info('--------- Starting Script ---------')
    main()
    log.info('--------- End Script ---------')
