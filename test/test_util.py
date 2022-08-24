import os
import random
import unittest

from bin import util
from bin.jira import Jira
from datetime import datetime

with open('/home/test/runs.txt') as f:
    lines = f.readlines()
    lines = [line.rstrip('\n') for line in lines]

RUN = random.choice(lines)


class TestStringMethods(unittest.TestCase):

    def test_slack_request(self):
        """
        Function should return false on invalid token
        """
        token = os.environ['SLACK_TOKEN']
        invalid_token = 0000

        with self.subTest():

            self.assertTrue(util.post_message_to_slack(
                'egg-test', token, 'test', True),
                'check if slack token in env is valid')

            self.assertFalse(util.post_message_to_slack(
                'egg-test', invalid_token, 'test', True),
                'slack_request returned True for invalid token')

    def test_directory_check(self):
        """
        Function should return True on existing directory e.g. /log
        """
        with self.subTest():
            os.mkdir('/exist')
            self.assertTrue(
                util.directory_check(['/exist']),
                'directory_check return wrong bool')
            self.assertFalse(
                util.directory_check(['/invisible_directory']),
                'directory_check return wrong bool')

    def test_dx_login(self):
        """
        Function should return False on invalid token
        """
        token = os.environ['DNANEXUS_TOKEN']
        invalid_token = 0000

        with self.subTest():
            self.assertTrue(
                util.dx_login(token), 'check dnanexus token in env')
            self.assertFalse(
                util.dx_login(invalid_token), 'dx_login return wrong value')

    def test_check_project_directory(self):
        """
        Function should return False if directory does not exist
        in staging52
        """
        token = os.environ['DNANEXUS_TOKEN']

        with self.subTest():
            self.assertTrue(util.check_project_directory(
                '220721_M03595_0385_000000000-KGLHN', token),
                'check_directory returned wrong value')
            # check within /processed
            self.assertTrue(util.check_project_directory(
                '200910_K00178_0279_BHH5WKBBXY_clinicalgenetics', token),
                'check_directory not checking within /processed folder')
            self.assertFalse(util.check_project_directory(
                'This_Should_Not_Exist', token),
                'check_directory return True for false folder')

    def test_get_describe_data(self):
        """
        Function should return empty if dx.describe() does not
        return anything for the specified project
        """
        token = os.environ['DNANEXUS_TOKEN']
        mock_run = '220316_A01295_0068_AH7H2GDMXY'

        with self.subTest():
            if util.dx_login(token):
                self.assertTrue(
                    isinstance(util.get_describe_data(mock_run, token), dict),
                    'get_describe not returning describe() for proper run')
                self.assertEqual(
                    len(util.get_describe_data(
                        'This_Should_Return_Empty', token)),
                    0, 'get_describe return is faulty')

    def test_read_pickle(self):
        """
        Function should return dict
        """
        self.assertTrue(
            isinstance(util.read_or_new_pickle('ansible.pickle'), dict))

    def test_get_next_month(self):
        """
        Function should return 1st of next month
        """
        today = datetime(2022, 1, 2, 15, 0, 0)
        date = util.get_next_month(today)

        with self.subTest():
            self.assertEqual(date.day, 1, 'get_month returned wrong day')
            self.assertGreater(
                date.month, today.month, 'get_month returned wrong month')

    def test_get_runs(self):
        """
        Function should return overlap in both /genetics
        and /log/dx-streaming-upload
        """
        mock_seq = 'A01295a'
        genetic_path = f'/genetics/{mock_seq}'
        logs_path = f'/logs/dx-streaming-upload/{mock_seq}'

        os.makedirs(f'{genetic_path}/{RUN}', exist_ok=True)
        os.makedirs(logs_path, exist_ok=True)

        open(f'{genetic_path}/{RUN}/content.txt', 'a').close()
        open(f'{logs_path}/run.{RUN}.lane.all.log', 'a').close()

        gene, log, tmp_seq = util.get_runs(
            [mock_seq], '/genetics', '/logs/dx-streaming-upload', {})

        with self.subTest():
            self.assertEqual(gene, log, 'get_run returns overlap error')
            self.assertEqual(len(tmp_seq), 1, 'get_run temp_seq faulty return')

    def test_check_age(self):
        """
        Function should return correct age validation
        and duration check
        """
        today = datetime(2022, 1, 1, 15, 0, 0)
        year_ago = datetime(2021, 1, 1, 15, 0, 0)
        recently = datetime(2021, 12, 1, 15, 0, 0)

        year_ago_epoch = year_ago.timestamp() * 1000
        ansible_week = os.environ['ANSIBLE_WEEK']
        mock_data = {
            'created': year_ago_epoch
        }

        old_enough, created_on, duration = util.check_age(
            mock_data, today, ansible_week)

        recently_epoch = recently.timestamp() * 1000
        mock_datab = {
            'created': recently_epoch
        }

        old_enoughb, created_onb, durationb = util.check_age(
            mock_datab, today, ansible_week)

        with self.subTest():
            self.assertTrue(old_enough, 'old_enough check faulty')
            self.assertEqual(
                created_on, '2021-01-01', 'created_on return not accurate')
            self.assertEqual(
                duration.days, 365, 'duration_check return faulty')

            self.assertFalse(old_enoughb, 'old_enough check faulty')
            self.assertEqual(
                created_onb, '2021-12-01', 'created_on return not accurate')
            self.assertEqual(
                durationb.days, 31, 'duration_check return faulty')

    def test_jira(self):
        """
        Function should return correct
        response for particular Jira issue
        """
        token = os.environ['JIRA_TOKEN']
        email = os.environ['JIRA_EMAIL']
        url = os.environ['JIRA_URL']

        jira = Jira(token, email, url)

        one_sample = '220304_A01295_0063_AH7TFVDMXY'
        project = 'EBH'
        data = jira.search_issue(
            one_sample, project_name=project, trimmed=True)

        multiple_sample = 'ansible'
        datab = jira.search_issue(
            multiple_sample, project_name=project, trimmed=True)

        assay, status, key = jira.get_issue_detail(one_sample)

        assayb, _, keyb = jira.get_issue_detail(multiple_sample)

        multiple_replies_sample = '220223_A01295_0059_AH5YL5DMXY'
        assayc, statusc, keyc = jira.get_issue_detail(multiple_replies_sample)

        with self.subTest():
            self.assertTrue(
                isinstance(data['issues'], dict),
                'search_issue not returning result for proper Jira issue')
            self.assertGreater(
                len(datab['issues']),
                1,
                'return 1 or no ticket for multiple-return ticket')

            self.assertEqual(
                [assay, status.upper(), key],
                ['TWE', 'ALL SAMPLES RELEASED', 'EBH-922'],
                'search_issue return faulty for single ticket')

            self.assertEqual(
                assayb,
                'More than 1 Jira ticket detected',
                'search_issue return faulty for multiple-ticket issue')
            self.assertIsNone(
                keyb,
                'search_issue return faulty for multiple-ticket issue')

            self.assertEqual(
                [assayc, statusc.upper(), keyc],
                ['TWE', 'ALL SAMPLES RELEASED', 'EBH-897'],
                'search_issue return faulty for RE: ticket')


if __name__ == '__main__':
    unittest.main()
