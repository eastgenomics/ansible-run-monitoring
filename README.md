# Ansible Run Monitoring

Script to automate deletion of local sequencing data from the server and notifying of stale runs (runs older than 1 day without associated Jira ticket or runs older than 30 days without Jira status `ALL SAMPLES RELEASED`). An alert will be sent to Slack before the deletion.

## Script Workflow

- Script will be scheduled to run every day by cron
- Compile list of runs in `/genetics`
- To qualify for automated deletion, each runs need to fulfill four main criteria: 
  - 002 project on DNANexus
  - Runs on uploaded to `001_Staging_Area52` DNAnexus project
  - Created `ANSIBLE_WEEK` ago
  - have Jira ticket with status `ALL SAMPLES RELEASED`
  - assay in `ANSIBLE_JIRA_ASSAY`
- Compile all qualified runs & save it to memory (pickle)
- Send Slack notification on stale run + alert on automated deletion roughly a week before deletion

## Rebuilding Docker Image

Run `docker build -t <image name> .`

## Running the Container
```
docker run --env-file <path to config> -v /genetics:/genetics -v /var/log/dx-streaming-upload:/log/dx-streaming-upload -v /var/log/monitoring:/log/monitoring <image name:tag>
```

## Config Env Variables

- `ANSIBLE_GENETICDIR`: the directory to look into for original genetic run. **This should be directory in docker container**
- `ANSIBLE_LOGSDIR`: the directory to look into for uploaded run logs **This should be directory in docker container**
- `ANSIBLE_SEQ`: sequencing machine, **use comma to include more machines** (e.g. a01295a, a01303b, a1405)
- `HTTP_PROXY`: http proxy
- `HTTPS_PROXY`: https proxy
- `ANSIBLE_WEEK `: how long before run is qualified as old e.g. 6 
- `DNANEXUS_TOKEN `: auth token for dxpy login
- `ANSIBLE_PICKLE_PATH`: directory to save memory e.g /log/monitoring
- `ANSIBLE_JIRA_ASSAY`: e.g. TWE,MYE **use comma to include multiple assays**
- `JIRA_TOKEN`: Jira API token
- `JIRA_EMAIL`: Jira API email
- `ANSIBLE_DEBUG`: (optional)
- `JIRA_API_URL`: Jira API Rest url
- `SLACK_NOTIFY_JIRA_URL`: Jira helpdesk queue url (for direct link to Jira sample ticket)
- `SLACK_TOKEN`: slack auth token
- `JIRA_PROJECT_ID`: Jira project id (helpdesk id e.g. EBHD, EBH)
- `JIRA_REPORTER_ID`: Jira reporter id for raising Jira issue

## Logging

Logging function is written in ` helper.py ` with format ` %(asctime)s:%(name)s:%(module)s:%(levelname)s:%(message)s `

E.g. ``` 2021-11-16 14:39:45,173```:```ansible main log```:```main```:```INFO```:```Fetching Dxpy API 211014_A01295_0031_AHL3MFDRXY started ```

Log file (``` ansible-run-monitoring.log ```) will be stored in ``` /log/monitoring/ansible-run-monitoring.log ``` in ansible server

## Automation

Cron has been scheduled to run the script daily

## Mock Testing

`Dockerfile.test` has been provided.

```
# Build the image
docker build -t ansible:test -f Dockerfile.test .

# Run a mock test
# Require mounting of /log/monitoring for storing memory, /genetics for mock create runs in /genetics directory
docker run --env-file <path to .env file> -v <path to /test/log/monitoring>:/log/monitoring -v <path to /test/genetics>:/genetics ansible:test /bin/bash -c "python -u mock.py && python -u main.py"

# Run unit test
docker run --env-file <path to .env file> ansible:test
```

## Error

If there's an error with the auth token for dnanexus, the error code below will be returned\
`" The token could not be found, code 401. Request Time=1637168014.38, Request ID=unavailable "`

For more information regarding the specific of error codes, please visit [here](https://documentation.dnanexus.com/developer/api/protocols).

Any bugs or suggestions for improvement, please raise an issue
