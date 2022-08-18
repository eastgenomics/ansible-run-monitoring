import os
import sys
import smtplib
import requests
import dxpy as dx

from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from tabulate import tabulate

from helper import get_logger

log = get_logger("util log")


def post_message_to_slack(channel: str, message: str, debug: bool) -> None:
    """
    Function to send Slack notification
    Inputs:
        channel: egg-alerts etc
        message: text
        debug: whether debug mode (channel: egg-test) or not
    Returns:
        dict: slack api response
    """

    log.info(f'Sending POST request to channel: #{channel}')

    if debug:
        channel = 'egg-test'

    try:
        response = requests.post('https://slack.com/api/chat.postMessage', {
            'token': os.environ['SLACK_TOKEN'],
            'channel': f'#{channel}',
            'text': message
        }).json()

        if response['ok']:
            log.info(f'POST request to channel #{channel} successful')
            return
        else:
            # slack api request failed
            error_code = response['error']
            log.error(error_code)

    except Exception as e:
        # endpoint request fail from server
        log.error(f'Error sending POST request to channel #{channel}')
        log.error(e)


def directory_check(directories: list) -> bool:

    """
    Function to check if directory exist
    Mainly to check if /genetic and /var/log/monitoring exist
    Input:
        directories: directory path
    Output: bool
    """

    for dir in directories:
        if os.path.isdir(dir):
            continue
        else:
            log.error(f'{dir} not found')
            return False

    return True


def dx_login(token: str) -> bool:

    """
    Function to check dxpy login
    Input: dxpy token
    Output: boolean
    """

    # try to get auth token from env (i.e. run in docker)
    try:
        DX_SECURITY_CONTEXT = {
            "auth_token_type": "Bearer",
            "auth_token": token
        }

        dx.set_security_context(DX_SECURITY_CONTEXT)
        dx.api.system_whoami()

        return True

    except Exception as error:
        log.error(error)

        return False


def check_project_directory(project: str):

    """
    Function to check if project is in staging52.
    Input:
        project: directory path
    Return:
        boolean
    """

    dx_obj = list(dx.find_data_objects(
        project='project-FpVG0G84X7kzq58g19vF1YJQ',
        folder=f'/{project}',
        limit=1)
    )

    if dx_obj:
        return True

    dx_obj = list(dx.find_data_objects(
        project='project-FpVG0G84X7kzq58g19vF1YJQ',
        folder=f'/processed/{project}',
        limit=1)
    )

    if dx_obj:
        return True

    return False


def get_describe_data(project: str):

    """
    Function to see if there is 002 project
    and its describe data
    Input:
        project: text
    Return:
        dict of project describe data
    """

    dxes = list(dx.search.find_projects(
        name=f'002_{project}.*',
        name_mode="regexp",
        describe=True,
        limit=1
        ))

    return dxes[0] if dxes else []


def send_mail(
        send_from: str,
        send_to: list,
        subject: str,
        server: str,
        port: int,
        df=None,
        files=None) -> None:

    """
    Function to send server email.
    Inputs:
        send_from: str
        send_to: list
        subject: text
        df: DataFrame or None
        files: list
    """

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

    try:
        smtp = smtplib.SMTP(server, port)

        log.info(f'Sending email to {COMMASPACE.join(send_to)}')
        smtp.sendmail(send_from, send_to, msg.as_string())
        log.info(f'Email to {COMMASPACE.join(send_to)} SENT')

        smtp.quit()

    except Exception as e:
        log.error(f'Send email function failed with error: {e}')
        message = (
            "Ansible-Monitoring: ERROR sending to helpdesk! Error Code: \n"
            f"`{e}`"
            )

        post_message_to_slack('egg-alerts', message)
