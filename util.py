import os
import sys
import smtplib

from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from tabulate import tabulate

from dotenv import load_dotenv
from helper import get_logger
import dxpy as dx
import datetime as dt

load_dotenv()

log = get_logger("util log")


def dx_login():

    """ Dxpy login user for dxpy function either by .env file or docker env """

    # try to get auth token from env (i.e. run in docker)
    try:
        AUTH_TOKEN = os.environ["AUTH_TOKEN"]
    except Exception as e:
        log.error('No dnanexus auth token detected')
        log.info('----- Stopping script -----')
        sys.exit()

    # env variable for dx authentication
    DX_SECURITY_CONTEXT = {
        "auth_token_type": "Bearer",
        "auth_token": AUTH_TOKEN
    }

    # set token to env
    log.info('Dxpy login initiated')
    dx.set_security_context(DX_SECURITY_CONTEXT)


def check_project_directory(project):

    """ Check if <project> directory is in Staging52. Return boolean """

    try:

        dxes = dx.find_data_objects(
            project='project-FpVG0G84X7kzq58g19vF1YJQ',
            folder=f'/{project}',
            limit=1
        )

        # if there is directory, this will not return empty list
        return_obj = list(dxes)

        if return_obj:
            return True

        return False

    except Exception as e:
        return False


def get_describe_data(project, sender, receivers):

    """ Find 002_ project directory. Return (dict) of the describe=True result.
    Else, will return empty list [] if no 002_ project is found.
    Exit script and send an error email
    if there is an issue with auth token for dxpy. """

    dxes = dx.search.find_projects(
        name=f'002_{project}_\D+',
        name_mode="regexp",
        describe=True
        )

    try:
        result = list(dxes)

    except Exception as e:

        # error handling in case auth_token expired or invalid
        log.error(e)

        send_mail(
            sender,
            receivers,
            'Ansible Run (Deletion) AUTH_TOKEN ERROR'
        )

        sys.exit()

    return result[0] if result else []


def send_mail(send_from, send_to, subject, df=None, files=None):

    """ Function to send email. Require send_to (list) and file (list) """

    assert isinstance(send_to, list)

    # email messge content
    text = """
        Here's the data for duplicated runs found in
        "/genetics" & "/var/log/dx-streaming-uploads" & DNAnexus:

        {table}

        Kind Regards,
        Beep Robot

    """

    html = """
        <html>
        <head>
        <style>
        table, th, td {{ border: 1px solid black; border-collapse: collapse; }}
        th, td {{ padding: 5px; }}
        </style>
        </head>
        <body>
        <p>
        Here's the data for duplicated runs found in
        "/genetics" & "/var/log/dx-streaming-uploads" & DNAnexus:
        </p>
        {table}
        <p>Kind Regards</p>
        <p>Beep Robot~</p>
        </body></html>
    """

    if df is not None:
        # we make df into table in email using tabulate

        col_header = list(df.columns.values)
        text = text.format(table=tabulate(
            df,
            headers=col_header,
            tablefmt="grid"))

        html = html.format(table=tabulate(
            df,
            headers=col_header,
            tablefmt="html"))

        msg = MIMEMultipart(
            "alternative", None, [MIMEText(text), MIMEText(html, 'html')])
    else:
        # if there is no dataframe (data), very likely there's an error
        # so we send an error code email

        text = """
            The dxpy auth token might be expired!
            Please check the log file for detailed error code.

            Kind Regards,
            Beep Robot

        """
        html = """
            <html>
            <head></head>
            <body>
            <p>
            The dxpy auth token might be expired!
            Please check the log file for detailed error code.
            </p>
            <p>Kind Regards</p>
            <p>Beep Robot~</p>
            </body></html>
        """
        msg = MIMEMultipart(
            "alternative", None, [MIMEText(text), MIMEText(html, 'html')])

    # email headers
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    # email message attachment (default: None)
    for f in files or []:
        with open(f, "rb") as fil:
            part = MIMEApplication(
                fil.read(),
                Name=basename(f)
            )
        # After the file is closed
        part['Content-Disposition'] = 'attachment; filename="%s"' % basename(f)
        msg.attach(part)

    # define server and port for smtp
    SERVER = os.environ['ENV_SERVER']
    PORT = int(os.environ['ENV_PORT'])

    try:
        smtp = smtplib.SMTP(SERVER, PORT)

        log.info(f'Send email to {COMMASPACE.join(send_to)}')
        smtp.sendmail(send_from, send_to, msg.as_string())
        log.info(f'Email to {COMMASPACE.join(send_to)} sent')

        smtp.quit()

    except Exception as e:
        log.error(f'Send email function failed with error: {e}')
