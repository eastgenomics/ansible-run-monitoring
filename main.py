import os
from login import dx_login
import dxpy as dx

dx_login()

WORKING_DIR = os.path.dirname(os.path.realpath(__file__))

print(f'Current Working Directory --> {WORKING_DIR}')

seq = ['A01295', 'A01305']

GENETIC_DIR = f'{WORKING_DIR}/genetics'
LOGS_DIR = f'{WORKING_DIR}/var/log/dx-streaming-upload'

duplicates = []
final_duplicates = []

for file in seq:
    gene_dir = f'{GENETIC_DIR}/{file}'
    logs_dir = f'{LOGS_DIR}/{file}'

    temp_duplicates = set([x.strip() for x in os.listdir(gene_dir)]) & set([os.path.splitext(x)[0].strip() for x in os.listdir(logs_dir)])

    duplicates += list(temp_duplicates)

for project in duplicates:

    dxes = dx.search.find_projects(name=f"002_{project}_\D+", name_mode="regexp")

    if not list(dxes):
        print(f'Project {project} not found')
        continue
    else:
        print(f'Project {project} --> found')
        final_duplicates.append(project)

# with open('duplicate.txt', 'w') as f:
#     f.write('\n'.join(final_duplicates))

print(final_duplicates)