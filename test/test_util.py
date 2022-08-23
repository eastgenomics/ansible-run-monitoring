import os
import random

from bin import util
from datetime import datetime
from dateutil.relativedelta import relativedelta

with open('/home/test/runs.txt') as f:
    lines = f.readlines()
    lines = [line.rstrip('\n') for line in lines]

RUN = random.choice(lines)


def test_slack_request():
    token = os.environ['SLACK_TOKEN']
    invalid_token = 0000

    assert util.post_message_to_slack(
        'egg-test', token, 'test', True) is True

    assert util.post_message_to_slack(
        'egg-test', invalid_token, 'test', True) is False


def test_directory_check():
    assert util.directory_check(['/log']) is True
    assert util.directory_check(['/invisible_directory']) is False


def test_dx_login():
    token = os.environ['DNANEXUS_TOKEN']
    invalid_token = 0000

    assert util.dx_login(token) is True
    assert util.dx_login(invalid_token) is False


def test_check_project_directory():
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
    token = os.environ['DNANEXUS_TOKEN']
    assert isinstance(util.get_describe_data(RUN, token), dict) is True
    assert len(util.get_describe_data('This_Should_Return_Empty', token)) == 0


def test_read_pickle():
    assert isinstance(util.read_or_new_pickle('ansible.pickle'), dict) is True


def test_get_next_month():
    today = datetime.now()
    date = util.get_next_month(today)

    assert date.day == 1

    if today.month == 12:
        assert date.month == 1
    else:
        assert date.month > today.month


def test_get_runs(tmp_path):
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
