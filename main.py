from dotenv import load_dotenv
import dxpy as dx

import os
import sys
import yaml


load_dotenv()


def dx_login():

    """ Authenticate login user for dxpy function either by .env file variable or docker environment """

    if len(sys.argv) > 1:
        # config / env file passed as arg
        # read in to dict and don't touch env variables
        AUTH_TOKEN = os.getenv("AUTH_TOKEN")
    else:
        # try to get auth token from env (i.e. run in docker)
        try:
            AUTH_TOKEN = os.environ["AUTH_TOKEN"]
        except NameError as e:
            raise NameError(
                'auth token could not be retrieved from environment and no .env file passed'
            )

    # env variable for dx authentication
    DX_SECURITY_CONTEXT = {
        "auth_token_type": "Bearer",
        "auth_token": AUTH_TOKEN
    }

    # set token to env
    dx.set_security_context(DX_SECURITY_CONTEXT)

def read_yaml(file_path):

    """ Function to read yaml config file (e.g. seq.yml) """

    with open(file_path, "r") as f:
        return yaml.safe_load(f)['seq']


# define number of seqs
seq = read_yaml('seq.yml')


def main():

    dx_login()

    # defining directories in docker container
    # Directories need to be mounted with docker run -v
    GENETIC_DIR = '/var/genetics'
    LOGS_DIR = '/var/log/dx-streaming-upload'

    duplicates = []
    final_duplicates = []

    # loop through each file in /genetics/<SEQ> and /var/log/dx-stream-upload/<SEQ>
    for file in seq:
        gene_dir = '{}/{}'.format(GENETIC_DIR, file)
        logs_dir = '{}/{}'.format(LOGS_DIR, file)

        # get the duplicates between two directories /genetics & /var/log/.. with sets
        temp_duplicates = set([x.strip() for x in os.listdir(gene_dir)]) & set([x.split('.')[1] for x in os.listdir(logs_dir)])

        duplicates += list(temp_duplicates)

    # find out if a run has been created for the project in dnanexus
    for project in duplicates:

        dxes = dx.search.find_projects(name="002_{}_\D+".format(project), name_mode="regexp")

        # if project not in return object, we leave it alone (continue)
        if not list(dxes):
            print('Project {} x found'.format(project))
            continue
        else:
            print('Project {} -> found'.format(project))
            final_duplicates.append(project)

    print('Before dx filtering: {}'.format(len(duplicates)))
    print('After dx filtering: {}'.format(len(final_duplicates)))

if __name__ == "__main__":
    main()