# Ansible Run Monitoring
### python v3.8.17

Script to automate deletion of local sequencing data and notifying of any runs that may require manual intervention. The script is designed to be added to a daily cronjob, and to delete data on a weekly basis on a Wednesday.

Runs will be automatically delete if they meet **all** the following criteria:

- uploaded to `001_Staging_Area52` DNAnexus project
- have a 002 DNAnexus project
- run folder created more than `ANSIBLE_WEEK` ago (as defined in config)
- have a Jira ticket with status `ALL SAMPLES RELEASED`, `DATA CANNOT BE PROCESSED` or `DATA CANNOT BE RELEASED`
- Jira ticket assay in `ANSIBLE_JIRA_ASSAY` (as defined in config)

Any runs that are old enough to be deleted but not meeting one or more of the above criteria will be flagged in a Slack alert sent on a Monday that may require manually deleting.

## Script Workflow

- Script scheduled to run everyday by cron on Ida server
- Compile all runs currently in `/genetics`
- Compile all runs that qualified for automated deletion & save it to memory (pickle)
- On a Monday, send Slack notification for runs that will be deleted on the following Wednesday and those that may require manual intervention


## Rebuilding Docker Image

Run `docker build -t <image name> .`

## Running the Container
```
docker run \
    --env-file <path to config> \
    -v <path to /genetics>:/genetics \
    -v <path to /var/log/dx-streaming-upload>:/log/dx-streaming-upload \
    -v <path to /var/log/monitoring>:/log/monitoring \
    <image name:tag> monitor.py
```

## Config Env Variables

- `HTTP_PROXY`: http proxy
- `HTTPS_PROXY`: https proxy
- `DNANEXUS_TOKEN `: auth token for dxpy login

- `ANSIBLE_WEEK `: how long before run is qualified as old enough to be deleted e.g. 2
- `ANSIBLE_GENETICDIR`: the directory to look into for original genetic run. **This should be directory in docker container**
- `ANSIBLE_LOGSDIR`: the directory to look into for uploaded run logs **This should be directory in docker container**
- `ANSIBLE_SEQ`: sequencing machine, **use comma to include more machines** (e.g. A01295a, A01295b, A01303a,A01303b)
- `ANSIBLE_PICKLE_PATH`: directory to save pickle file for runs to be deleted e.g `/log/monitoring`
- `ANSIBLE_JIRA_ASSAY`: e.g. CEN,TWE,TSO500,MYE **use comma to include multiple assays**
- `ANSIBLE_DEBUG`: (optional)

- `JIRA_TOKEN`: Jira API token
- `JIRA_EMAIL`: Jira API email
- `JIRA_API_URL`: Jira API Rest url
- `JIRA_PROJECT_ID`: Jira project id (helpdesk id e.g. EBHD, EBH)
- `JIRA_REPORTER_ID`: Jira reporter id for raising Jira issue

- `SLACK_NOTIFY_JIRA_URL`: Jira helpdesk queue url (for direct link to Jira sample ticket)
- `SLACK_TOKEN`: slack auth token


## Logging

Logging function is written in ` helper.py ` with format ` %(asctime)s:%(name)s:%(module)s:%(levelname)s:%(message)s `

E.g. ``` 2021-11-16 14:39:45,173```:```ansible main log```:```main```:```INFO```:```Fetching Dxpy API 211014_A01295_0031_AHL3MFDRXY started ```

Log file (``` ansible-run-monitoring.log ```) will be stored in ``` /log/monitoring/ansible-run-monitoring.log ``` in ansible server

## Automation

Cron scheduled to run the script daily


## Simulated Testing

A script has been provided to test running of the monitoring on each day of the week to check the observed behaviour is as expected. This creates local test directories and Jira tickets, runs the simulated checks and then clears up the test data. The following test runs and expected behaviour is set up:

- Run 1 - not old enough to be deleted => skipped
- Run 2 - no data found in StagingArea52 => alert for manual intervention
- Run 3 - no 002 DNAnexus project found => alert for manual intervention
- Run 4 - run uploaded and processed but Jira ticket not in correct state (i.e. still in processing) => alert for manual intervention
- Run 5 - run processed and ticket released state => flag for deletion
- Run 6 - ticket at `Data cannot be processed` (i.e. suggests failed sequencing) => flag for deletion
- Run 7 - ticket at `Data cannot be released` (i.e. processed but failed QC) => f lag for deletion

A Slack alert should be observed once for runs 2, 3 and 4 for manual intervention and once for runs 5, 6 and 7 for deletion. Deletion will then run on the simulated Wednesday for runs 5, 6 and 7 then nothing else external should happen for Thursday - Sunday aside from running of the script and logging.

The same environment variables as listed above are required, and `ANSIBLE_WEEK` should be set to 2 to run the test.

To run the simulated testing inside a Docker container:
```
docker run \
    --env-file <path to config> \
    -v <path to /genetics>:/genetics \
    -v <path to /var/log/dx-streaming-upload>:/log/dx-streaming-upload \
    -v <path to /var/log/monitoring>:/log/monitoring \
    <image name:tag> simulate_test_runs.py
```


## Error

If there's an error with the auth token for dnanexus, the error code below will be returned\
`" The token could not be found, code 401. Request Time=1637168014.38, Request ID=unavailable "`

For more information regarding the specific of error codes, please visit [here](https://documentation.dnanexus.com/developer/api/protocols).

Any bugs or suggestions for improvement, please raise an issue
