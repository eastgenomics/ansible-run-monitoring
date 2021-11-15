from dotenv import load_dotenv
import dxpy as dx

import os
import sys
import yaml
import smtplib
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from tabulate import tabulate
import pandas as pd
import datetime


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

def send_mail(send_from, send_to, subject, df, files=None):

    """ Function to send email. Require send_to (list) and file (list) """

    assert isinstance(send_to, list)

    # msg = MIMEMultipart()

    # email messge content
    text = """
        Hi,

        Here's the data:

        {table}

        Kind Regards,
        Beep~

    """

    html = """
        <html>
        <head>
        <style> 
        table, th, td {{ border: 1px solid black; border-collapse: collapse; }}
        th, td {{ padding: 5px; }}
        </style>
        </head>
        <body><p>Hi</p>
        <p>Here is the data:</p>
        {table}
        <p>Kind Regards</p>
        <p>Beep~</p>
        </body></html>
    """

    col_header = list(df.columns.values)
    text = text.format(table=tabulate(df, headers=col_header, tablefmt="grid"))
    html = html.format(table=tabulate(df, headers=col_header, tablefmt="html"))
    
    msg = MIMEMultipart(
        "alternative", None, [MIMEText(text), MIMEText(html,'html')])

    # email headers
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    # email message attachment
    for f in files or []:
        with open(f, "rb") as fil:
            part = MIMEApplication(
                fil.read(),
                Name=basename(f)
            )
        # After the file is closed
        part['Content-Disposition'] = 'attachment; filename="%s"' % basename(f)
        msg.attach(part)


    smtp = smtplib.SMTP('smtp.net.addenbrookes.nhs.uk', 25)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.quit()

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