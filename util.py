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

load_dotenv()

log = get_logger("ansible util log")


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


def send_mail(send_from, send_to, subject, df=None, files=None):

    """ Function to send email. Require send_to (list) and file (list) """

    assert isinstance(send_to, list)

    # email messge content
    text = """
        Hi,

        Here's the data for duplicated runs found in
        /genetics & /var/log/dx-streaming-uploads & dnaNexus:

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
        <body><p>Hi</p>
        <p>
        Here's the data for duplicated runs found in
        /genetics & /var/log/dx-streaming-uploads & dnaNexus:
        </p>
        {table}
        <p>Kind Regards</p>
        <p>Beep Robot~</p>
        </body></html>
    """

    if df is not None:
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
        msg = MIMEMultipart()
        msg.attach(
            MIMEText(
                """

                The authentication for dxpy has returned an error.
                Please check log file

                """
            ))

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

    SERVER = os.environ['ENV_SERVER']
    PORT = int(os.environ['ENV_PORT'])

    try:
        smtp = smtplib.SMTP(SERVER, PORT)

        log.info('Send email to {}'.format(COMMASPACE.join(send_to)))
        smtp.sendmail(send_from, send_to, msg.as_string())
        log.info('Email to {} sent'.format(COMMASPACE.join(send_to)))

        smtp.quit()

    except Exception as e:
        log.error('Send email function failed with error: {}'.format(e))
