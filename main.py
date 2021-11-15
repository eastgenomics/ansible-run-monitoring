import os
import datetime
import pandas as pd
import dxpy as dx

from util import dx_login, send_mail


seq = [x.upper() for x in os.environ['ENV_SEQ'].split(',')]

def main():

    dx_login()

    #defining environment variables
    GENETIC_DIR = os.environ['ENV_GENETICDIR']
    LOGS_DIR = os.environ['ENV_LOGSDIR']

    sender = os.environ['ENV_SENDER']
    receivers =os.environ['ENV_RECEIVERS']
    receivers = receivers.split(',') if ',' in receivers else [receivers]

    duplicates = []
    final_duplicates = []
    table_data = []

    # loop through each file in /genetics/<SEQ> and /var/log/dx-stream-upload/<SEQ>
    for file in seq:
        gene_dir = '{}/{}'.format(GENETIC_DIR, file)
        logs_dir = '{}/{}'.format(LOGS_DIR, file)

        # get the duplicates between two directories /genetics & /var/log/.. with sets
        temp_duplicates = set(
            [x.strip() for x in os.listdir(gene_dir)]) & set([x.split('.')[1] for x in os.listdir(logs_dir)]
        )

        duplicates += list(temp_duplicates)

    # find out if a run has been created for the project in dnanexus
    for project in duplicates:
        
        # generator object only allows one read, similar to python3 map generator object
        dxes = dx.search.find_projects(
            name="002_{}_\D+".format(project), 
            name_mode="regexp", 
            describe=True
            )
        
        # save return object into an external variable for later manipulation
        return_obj = list(dxes)

        # if return=True, we know the proj exist in dnaNexus: append to final_duplicates list
        # append most describe=True data to table_data (list of tuples): for dataframe creation later
        if return_obj:
            proj_des = return_obj[0]['describe']

            # convert millisec from Epoch datetime to readable human format
            created_date = datetime.datetime.fromtimestamp(proj_des['created'] / 1000.0).strftime('%Y-%m-%d')
            
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

    duplicates_dir = []

    # create the directories path for each runs (genetics & logs) for writing to txt file
    for file in final_duplicates:
        duplicates_dir.append('/genetics/{}/{}'.format(file.split('_')[1], file))
        duplicates_dir.append('/var/log/dx-streaming-upload/{}/run.{}.lane.all.log'.format(file.split('_')[1], file))

    # saving the directories into txt file (newline)
    with open('duplicates.txt', 'w') as f:
        f.write('\n'.join(duplicates_dir))

    # dataframe creation for all runs describe=True data
    df = pd.DataFrame(
        table_data, 
        columns =['Project Name', 'Created', 'Data Usage', 'Created By', 'Storage Cost']
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