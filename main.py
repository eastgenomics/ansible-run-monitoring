import os
import sys
from datetime import datetime
import pandas as pd
import shutil

from bin.util import *
from bin.helper import get_logger
from bin.jira import Jira

log = get_logger("main log")


def main():

    # importing env variables
    try:
        GENETIC_DIR = os.environ['ANSIBLE_GENETICDIR']
        LOGS_DIR = os.environ['ANSIBLE_LOGSDIR']
        ANSIBLE_WEEK = int(os.environ['ANSIBLE_WEEK'])
        PICKLE_PATH = os.environ['ANSIBLE_PICKLE_PATH']

        DEBUG = os.environ.get('ANSIBLE_DEBUG', False)

        DNANEXUS_TOKEN = os.environ["DNANEXUS_TOKEN"]
        SLACK_TOKEN = os.environ['SLACK_TOKEN']

        JIRA_TOKEN = os.environ['JIRA_TOKEN']
        JIRA_EMAIL = os.environ['JIRA_EMAIL']
        JIRA_ASSAY = [
            a.strip() for a in os.environ['ANSIBLE_JIRA_ASSAY'].split(',')]
        JIRA_API_URL = os.environ['JIRA_API_URL']
        JIRA_SLACK_URL = os.environ['SLACK_NOTIFY_JIRA_URL']
        JIRA_PROJECT_ID = os.environ['JIRA_PROJECT_ID']
        JIRA_REPORTER_ID = os.environ['JIRA_REPORTER_ID']

        SEQS = [x.strip() for x in os.environ['ANSIBLE_SEQ'].split(',')]
    except KeyError as e:
        log.error(f'Failed to import env {e}')
        sys.exit('END SCRIPT')

    # log debug status
    if DEBUG:
        log.info('Running in DEBUG mode')
        ANSIBLE_PICKLE = f'{PICKLE_PATH}/ansible_dict.test.pickle'
    else:
        log.info('Running in PRODUCTION mode')
        ANSIBLE_PICKLE = f'{PICKLE_PATH}/ansible_dict.pickle'

    # dxpy login
    if not dx_login(DNANEXUS_TOKEN):
        message = "ANSIBLE-MONITORING: ERROR with dxpy login!"

        post_message_to_slack('egg-alerts', SLACK_TOKEN, message, DEBUG)
        sys.exit('END SCRIPT')

    # check if /genetics & /logs/dx-streaming-upload exist
    if not directory_check([GENETIC_DIR, LOGS_DIR]):
        message = f"ANSIBLE-MONITORING: ERROR with missing directory!"

        post_message_to_slack('egg-alerts', SLACK_TOKEN, message, DEBUG)
        sys.exit('END SCRIPT')

    # get script run date
    today = datetime.today()
    log.info(today)

    # read memory in /var/log/monitoring
    ansible_pickle = read_or_new_pickle(ANSIBLE_PICKLE)
    runs = ansible_pickle.keys()

    jira = Jira(JIRA_TOKEN, JIRA_EMAIL, JIRA_API_URL, DEBUG)

    # get /genetic disk usage stat
    init_usage = shutil.disk_usage(GENETIC_DIR)

    if today.day == 1:
        # run deletion on the 1st
        tmp_delete = collections.defaultdict(dict)
        if runs:
            for run in runs:

                # last check to see if status is still
                # ALL-SAMPLES-RELEASED
                _, status, _ = jira.get_issue_detail(run)

                seq = ansible_pickle[run]['seq']
                key = ansible_pickle[run]['key']
                assay = ansible_pickle[run]['assay']
                size = ansible_pickle[run]['size']

                if status.upper() != 'ALL SAMPLES RELEASED':
                    log.info(f'SKIP {GENETIC_DIR}/{seq}/{run}')
                    continue

                assert seq.strip(), 'sequencer is empty'
                assert run.strip(), 'run ID is empty'

                try:
                    log.info(f'DELETING {GENETIC_DIR}/{seq}/{run}')
                    shutil.rmtree(f'{GENETIC_DIR}/{seq}/{run}')

                    tmp_delete[run]['seq'] = seq
                    tmp_delete[run]['status'] = status
                    tmp_delete[run]['key'] = key
                    tmp_delete[run]['assay'] = assay
                    tmp_delete[run]['size'] = size

                    # write to /log just for own record
                    with open('/log/monitoring/ansible_delete.txt', 'a') as f:
                        f.write(f'{GENETIC_DIR}/{seq}/{run} {today}' + '\n')

                except OSError as e:
                    # if deletion failed
                    # clear memory & end script
                    log.error(e)
                    clear_memory(ANSIBLE_PICKLE)

                    msg = "ANSIBLE-MONITORING: ERROR with file deletion!"
                    post_message_to_slack(
                        'egg-alerts', SLACK_TOKEN, msg, DEBUG)

                    sys.exit('END SCRIPT')

        if tmp_delete:
            # something has been deleted
            # create a Jira ticket for acknowledgement

            # get after deletion disk usage
            post_usage = shutil.disk_usage(GENETIC_DIR)
            # make datetime into str type
            jira_date = today.strftime('%d/%m/%Y')

            # format disk usage for jira issue description
            init_total = round(init_usage[0] / 1024 / 1024 / 1024, 2)
            init_used = round(init_usage[1] / 1024 / 1024 / 1024, 2)
            init_percent = round((init_usage[1] / init_usage[0]) * 100, 2)

            p_total = round(post_usage[0] / 1024 / 1024 / 1024, 2)
            p_used = round(post_usage[1] / 1024 / 1024 / 1024, 2)
            p_percent = round((post_usage[1] / post_usage[0]) * 100, 2)

            # format deleted run for issue description
            jira_data = [
                '{} in /genetics/{}'.format(k, v['seq'])
                for k, v in tmp_delete.items()]

            # description body
            body = '\n'.join(jira_data)

            desc = f'Runs deleted on {jira_date}\n'

            # all disk space data
            disk_usage = (
                '\n/genetics disk usage before: '
                f'{init_used} / {init_total} {init_percent}%'
                '\n/genetics disk usage after: '
                f'{p_used} / {p_total} {p_percent}%'
            )

            desc += body + disk_usage

            # create Jira issue
            # issue type for acknowledgement 10124
            # helpdesk 10042 for debug 10040 for prod

            log.info('Creating Jira acknowledgement issue')
            response = jira.create_issue(
                f'{jira_date} Deleted Runs In 10.252.166.184',
                10124,
                JIRA_PROJECT_ID,
                JIRA_REPORTER_ID,
                3,
                desc,
                False)

            if 'id' in response:
                # log the raised issue key for reference in future
                issue_key = response['key']
                log.info(f'{issue_key} {JIRA_PROJECT_ID}')
            else:
                # if jira ticket creation issue
                # send msg to Slack - stop script
                err_msg = response['errors']
                msg = "ANSIBLE-MONITORING: ERROR with creating Jira ticket!"
                msg += f'\n`{err_msg}`'
                post_message_to_slack('egg-alerts', SLACK_TOKEN, msg, DEBUG)

                log.error(response)
                sys.exit('END SCRIPT')

    elif today.day >= 17 and today.day < 24:
        # if today is nearing 24th
        alert_day = get_next_month(today, 24)

        # check if coming 24th falls in weekend
        if alert_day.isoweekday() in [6, 7]:
            # if so, get the coming Friday
            friday = get_weekday(alert_day, 5, False)

            if today == friday:
                # send alert about deletion
                log.info(today)
                if runs:
                    post_message_to_slack(
                        'egg-logs',
                        SLACK_TOKEN,
                        ansible_pickle,
                        DEBUG,
                        usage=init_usage,
                        today=today,
                        jira_url=JIRA_SLACK_URL,
                        notification=True)
                else:
                    log.info('NO RUNS IN MEMORY DETECTED')
            else:
                pass

    elif today.day == 24:
        if runs:
            post_message_to_slack(
                'egg-logs',
                SLACK_TOKEN,
                ansible_pickle,
                DEBUG,
                usage=init_usage,
                today=today,
                jira_url=JIRA_SLACK_URL,
                notification=True)
        else:
            log.info('NO RUNS IN MEMORY DETECTED')

    temp_pickle = collections.defaultdict(dict)
    temp_stale = collections.defaultdict(dict)

    genetic_directory, logs_directory, tmp_seq = get_runs(
        SEQS, GENETIC_DIR, LOGS_DIR)

    # Get the duplicates between two directories /genetics & /var/log/
    temp_duplicates = set(genetic_directory) & set(logs_directory)

    log.info(f'Number of overlap files: {len(temp_duplicates)}')

    # for each project, we check if it exists on DNANexus
    for project in list(temp_duplicates):

        # check if proj in staging52
        uploaded = check_project_directory(project)

        # get the sequencer the proj is in
        seq = tmp_seq[project]

        # get project size
        run_path = f'{GENETIC_DIR}/{seq}/{project}'
        run_size = get_size(run_path)

        # get 002 proj describe data
        project_data = get_describe_data(project)

        # get run created date
        created_date = get_date(os.path.getmtime(run_path))
        created_on = created_date.strftime('%Y-%m-%d')
        duration = get_duration(today, created_date)

        # check age of run
        old_enough = check_age(created_date, today, ANSIBLE_WEEK)

        # get proj jira details
        assay, status, key = jira.get_issue_detail(project)

        if project_data and uploaded:
            # found the 002 project & found in staging52

            data = project_data['describe']
            trimmed_id = data['id'].lstrip('project-')
            DX_URL = 'https://platform.dnanexus.com/panx/projects'

            if old_enough:
                # run is old enough meaning
                # been there for more than ANSIBLE_WEEK

                if (
                        status.upper() == 'ALL SAMPLES RELEASED' and
                        assay in JIRA_ASSAY):

                    # Jira ticket is ALL SAMPLES RELEASED
                    # and assay in listed assays

                    # will be marked for deletion
                    temp_pickle[project] = {
                        'seq': seq,
                        'status': status,
                        'key': key,
                        'assay': assay,
                        'created': created_on,
                        'duration': round(duration.days / 7, 2),
                        'old_enough': old_enough,
                        'url': f'{DX_URL}/{trimmed_id}/data',
                        'size': run_size
                    }

                    log.info('{} {} ::: {} weeks PASS'.format(
                        project,
                        created_on,
                        duration.days / 7))

                    continue
                else:
                    # Jira status not 'ALL SAMPLES RELEASED'
                    # or assay incorrect
                    log.info('{} {} ::: {} weeks FAILED JIRA'.format(
                        project,
                        created_on,
                        round(duration.days / 7, 2)))

                    if key is None or assay in JIRA_ASSAY:
                        # have 002 project & old enough
                        # Have no Jira ticket
                        # or Jira ticket not All RELEASED

                        # check if stale
                        temp_stale[project] = {
                            'seq': seq,
                            'status': status,
                            'key': key,
                            'assay': assay,
                            'created': created_on,
                            'duration': round(duration.days / 7, 2),
                            'old_enough': old_enough,
                            'url': f'{DX_URL}/{trimmed_id}/data',
                            'size': run_size
                        }

                    continue
            else:
                # runs not old enough meaning
                # runs have not been ther e for longer
                # than ANSIBLE_WEEK
                # won't be marked for deletion

                log.info('{} {} ::: {} weeks NOT OLD'.format(
                    project,
                    created_on,
                    round(duration.days / 7, 2)))

                if key is None or assay in JIRA_ASSAY:
                    # have 002 project & not old enough
                    # Jira ticket - no idea

                    # check if stale
                    temp_stale[project] = {
                        'seq': seq,
                        'status': status,
                        'key': key,
                        'assay': assay,
                        'created': created_on,
                        'duration': round(duration.days / 7, 2),
                        'old_enough': old_enough,
                        'url': f'{DX_URL}/{trimmed_id}/data',
                        'size': run_size
                    }

                continue
        else:
            # either no 002 project found
            # or not uploaded to staging52
            log.info('{} {} ::: {} weeks FAILED'.format(
                    project,
                    created_on,
                    round(duration.days / 7, 2)))
            continue

    log.info(f'Stale runs to check: {len(temp_stale)}')
    log.info(f'{len(temp_pickle.keys())} marked for deletion')

    if today.day < 23:
        # we send countdown / alert on either
        # 24th or 25th depending on cron schedule
        # as long as it's before 23rd, we save to memory
        # on run which qualify for deletion

        log.info('Writing into pickle file')
        with open(ANSIBLE_PICKLE, 'wb') as f:
            pickle.dump(temp_pickle, f)

    # send about stale run
    post_message_to_slack(
        'egg-logs',
        SLACK_TOKEN,
        temp_stale,
        DEBUG,
        usage=init_usage,
        today=today,
        jira_url=JIRA_SLACK_URL,
        notification=True,
        stale=True)


if __name__ == "__main__":
    log.info('STARTING SCRIPT')
    main()
    log.info('END SCRIPT')
