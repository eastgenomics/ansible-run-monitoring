import os
import sys
import datetime as dt
import pandas as pd
import dxpy as dx

from util import dx_login, send_mail


def main():

    dx_login()

    # Defining environment variables
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
        gene_dir = '{}/{}'.format(GENETIC_DIR, file)
        logs_dir = '{}/{}'.format(LOGS_DIR, file)

        # Get the duplicates between two directories /genetics & /var/log/
        gene_dir = set([x.strip() for x in os.listdir(gene_dir)])
        logs_dir = set([x.split('.')[1] for x in os.listdir(logs_dir)])

        temp_duplicates = gene_dir & logs_dir

        duplicates += list(temp_duplicates)

    # find out if a run has been created for the project in dnanexus
    for project in duplicates:
        # dxpy to query project in dnanexus
        dxes = dx.search.find_projects(
            name="002_{}_\D+".format(project),
            name_mode="regexp",
            describe=True
            )

        # save return object into an external variable for later manipulation
        return_obj = list(dxes)

        # if return=True, 002_run is created in dnanexus
        if return_obj:
            proj_des = return_obj[0]['describe']

            today = dt.datetime.today()

            # convert millisec from Epoch datetime to readable human format
            created_date = dt.datetime.fromtimestamp(proj_des['created'] / 1000.0).strftime('%Y-%m-%d')

            duration = today - created_date

            # check if created_date is more than 3 months (90 days)
            if duration.total_seconds() / (24*60*60) > 90:

                table_data.append(
                    (
                        project,
                        created_date,
                        '{} GB'.format(round(proj_des['dataUsage'])),
                        proj_des['createdBy']['user'],
                        proj_des['storageCost']
                    )
                )

                final_duplicates.append(project)

    if not final_duplicates:
        print('There is no runs older than 3 months')
        sys.exit()

    duplicates_dir = []

    # create the directories path for each delete-able run
    for file in final_duplicates:
        fileseq = file.split('_')[1]
        duplicates_dir.append('/genetics/{}/{}'.format(fileseq, file))
        duplicates_dir.append('/var/log/dx-streaming-upload/{}/run.{}.lane.all.log'.format(fileseq, file))

    # saving the directories into txt file (newline)
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
            'Storage Cost'
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
    main()
