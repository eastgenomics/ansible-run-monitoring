import os
import pandas as pd
import dxpy as dx
import datetime

from util import read_yaml, dx_login, send_mail


# define number of seqs
seq = read_yaml('seq.yml')


def main():

    dx_login()

    # defining directories in docker container
    # Directories need to be mounted with docker run -v
    GENETIC_DIR = 'var/genetics'
    LOGS_DIR = 'var/log/dx-streaming-upload'

    duplicates = []
    final_duplicates = []
    table_data = []

    # loop through each file in /genetics/<SEQ> and /var/log/dx-stream-upload/<SEQ>
    for file in seq:
        gene_dir = '{}/{}'.format(GENETIC_DIR, file)
        logs_dir = '{}/{}'.format(LOGS_DIR, file)

        # get the duplicates between two directories /genetics & /var/log/.. with sets
        temp_duplicates = set([x.strip() for x in os.listdir(gene_dir)]) & set([x.split('.')[1] for x in os.listdir(logs_dir)])

        duplicates += list(temp_duplicates)

    # find out if a run has been created for the project in dnanexus
    for project in duplicates:
        
        # careful generator object only allows one read, similar to python3 map generator object
        dxes = dx.search.find_projects(name="002_{}_\D+".format(project), name_mode="regexp", describe=True)
        return_obj = list(dxes)

        if return_obj:
            proj_des = return_obj[0]['describe']
            
            table_data.append(
                (project, datetime.datetime.fromtimestamp(proj_des['created'] / 1000.0).strftime('%Y-%m-%d'), '{} GB'.format(round(proj_des['dataUsage'])), proj_des['createdBy']['user'], proj_des['storageCost'])
                )

            final_duplicates.append(project)

    duplicates_dir = []

    # create the directories path for each runs (genetics & logs)
    for file in final_duplicates:
        duplicates_dir.append('/genetics/{}/{}'.format(file.split('_')[1], file))
        duplicates_dir.append('/var/log/dx-streaming-upload/{}/run.{}.lane.all.log'.format(file.split('_')[1], file))

    # saving the directories into txt file
    with open('duplicates.txt', 'w') as f:
        f.write('\n'.join(duplicates_dir))


    df = pd.DataFrame(table_data, columns =['Project Name', 'Created', 'Data Usage', 'Created By', 'Storage Cost'])

    print(df.head())

    sender = 'BioinformaticsTeamGeneticsLab@addenbrookes.nhs.uk'
    receiver = ['jason.ling@addenbrookes.nhs.uk']

    send_mail(
        sender,
        receiver,
        'Ansible Run (Deletion)', 
        df, 
        ['duplicates.txt']
    )

if __name__ == "__main__":
    main()