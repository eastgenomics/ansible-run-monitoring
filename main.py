from dotenv import load_dotenv
import dxpy as dx

import os
import sys

load_dotenv()

def dx_login():

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

    print(f'Authentication Token: {AUTH_TOKEN}')

    # env variable for dx authentication
    DX_SECURITY_CONTEXT = {
        "auth_token_type": "Bearer",
        "auth_token": AUTH_TOKEN
    }

    # set token to env
    dx.set_security_context(DX_SECURITY_CONTEXT)

dx_login()

WORKING_DIR = os.path.dirname(os.path.realpath(__file__))

print(f'Current Working Directory: {WORKING_DIR}')

seq = ['A01295', 'A01303']

GENETIC_DIR = f'{WORKING_DIR}/genetics'
LOGS_DIR = f'{WORKING_DIR}/var/log/dx-streaming-upload'

duplicates = []
final_duplicates = []

for file in seq:
    gene_dir = f'{GENETIC_DIR}/{file}'
    logs_dir = f'{LOGS_DIR}/{file}'

    temp_duplicates = set([x.strip() for x in os.listdir(gene_dir)]) & set([x.split('.')[1] for x in os.listdir(logs_dir)])

    duplicates += list(temp_duplicates)

for project in duplicates:

    dxes = dx.search.find_projects(name=f"002_{project}_\D+", name_mode="regexp")

    if not list(dxes):
        print(f'Project {project} not found')
        continue
    else:
        print(f'Project {project} --> found')
        final_duplicates.append(project)

print(f'Before dx filtering: {len(duplicates)}')
print(f'After dx filtering: {len(final_duplicates)}')