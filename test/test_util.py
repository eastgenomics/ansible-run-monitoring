import os
import random

from bin import util
from bin.jira import Jira
from datetime import datetime
from dateutil.relativedelta import relativedelta

with open('/home/test/runs.txt') as f:
    lines = f.readlines()
    lines = [line.rstrip('\n') for line in lines]

RUN = random.choice(lines)


def test_slack_request():
    """
    Function should return false on invalid token
    """
    token = os.environ['SLACK_TOKEN']
    invalid_token = 0000

    assert util.post_message_to_slack(
        'egg-test', token, 'test', True) is True

    assert util.post_message_to_slack(
        'egg-test', invalid_token, 'test', True) is False


def test_directory_check():
    """
    Function should return True on existing directory e.g. /log
    """
    assert util.directory_check(['/log']) is True
    assert util.directory_check(['/invisible_directory']) is False


def test_dx_login():
    """
    Function should return False on invalid token
    """
    token = os.environ['DNANEXUS_TOKEN']
    invalid_token = 0000

    assert util.dx_login(token) is True
    assert util.dx_login(invalid_token) is False


def test_check_project_directory():
    """
    Function should return False if directory does not exist
    in staging52
    """
    token = os.environ['DNANEXUS_TOKEN']
    invalid_token = 0000

    assert util.check_project_directory(
        '220721_M03595_0385_000000000-KGLHN', token) is True
    assert util.check_project_directory(
        '220114_A01295_0045_AHV3LVDRXY', token) is True
    assert util.check_project_directory(
        'This_Should_Not_Exist', token) is False
    assert util.check_project_directory(
        '220721_M03595_0385_000000000-KGLHN', invalid_token) is False


def test_get_describe_data():
    """
    Function should return empty if dx.describe() does not
    return anything for the specified project
    """
    token = os.environ['DNANEXUS_TOKEN']
    mock_run = '220316_A01295_0068_AH7H2GDMXY'
    assert isinstance(util.get_describe_data(mock_run, token), dict) is True
    assert len(util.get_describe_data('This_Should_Return_Empty', token)) == 0


def test_read_pickle():
    """
    Function should return dict
    """
    assert isinstance(util.read_or_new_pickle('ansible.pickle'), dict) is True


def test_get_next_month():
    """
    Function should return 1st of next month
    """
    today = datetime(2022, 1, 2, 15, 0, 0)
    date = util.get_next_month(today)

    assert date.day == 1
    assert date.month > today.month


def test_get_runs(tmp_path):
    """
    Function should return overlap in both /genetics
    and /log/dx-streaming-upload
    """
    g = tmp_path / "genetics"
    lg = tmp_path / "logs"
    g.mkdir()
    lg.mkdir()

    dx = lg / "dx-streaming-upload"
    dx.mkdir()

    mock_seq = 'A01295a'

    gm = g / mock_seq
    dxm = dx / mock_seq
    gm.mkdir()
    dxm.mkdir()

    gmr = gm / RUN
    dxmr = dxm / f'run.{RUN}.lane.all.log'
    gmr.mkdir()
    dxmr.write_text('This is a log file')

    gmrf = gmr / 'content.txt'
    gmrf.write_text('This is a content file')

    gene, log = util.get_runs([mock_seq], g, dx, {})

    assert gene == log


def test_check_age():
    today = datetime(2022, 1, 1, 15, 0, 0)
    year_ago = datetime(2021, 1, 1, 15, 0, 0)
    recently = datetime(2021, 12, 1, 15, 0, 0)

    assert year_ago < today

    year_ago_epoch = year_ago.timestamp() * 1000
    ansible_week = os.environ['ANSIBLE_WEEK']
    mock_data = {
        'created': year_ago_epoch
    }

    old_enough, created_on, duration = util.check_age(
        mock_data, today, ansible_week)

    assert old_enough is True
    assert created_on == '2021-01-01'
    assert duration.days == 365

    recently_epoch = recently.timestamp() * 1000
    mock_data = {
        'created': recently_epoch
    }

    old_enough, created_on, duration = util.check_age(
        mock_data, today, ansible_week)

    assert old_enough is False
    assert created_on == '2021-12-01'
    assert duration.days == 31


def test_jira():
    token = os.environ['JIRA_TOKEN']
    email = os.environ['JIRA_EMAIL']
    url = os.environ['JIRA_URL']

    jira = Jira(token, email, url)

    one_sample = '220304_A01295_0063_AH7TFVDMXY'
    project = 'EBH'
    data = jira.search_issue(one_sample, project_name=project, trimmed=True)
    assert isinstance(data['issues'], dict)

    multiple_sample = 'ansible'
    data = jira.search_issue(
        multiple_sample, project_name=project, trimmed=True)
    assert len(data['issues']) > 1

    assay, status, key = jira.get_issue_detail(one_sample)
    assert assay == 'TWE'
    assert status.upper() == 'ALL SAMPLES RELEASED'
    assert key == 'EBH-922'

    assay, status, key = jira.get_issue_detail(multiple_sample)
    assert assay == 'More than 1 Jira ticket detected'
    assert status == 'More than 1 Jira ticket detected'
    assert key is None

    multiple_replies_sample = '220223_A01295_0059_AH5YL5DMXY'
    assay, status, key = jira.get_issue_detail(multiple_replies_sample)
    assert assay == 'TWE'
    assert status.upper() == 'ALL SAMPLES RELEASED'
    assert key == 'EBH-897'
