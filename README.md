# Ansible Run Monitoring

Script to automate deletion of qualified runs in `/genetics` and notifying of stale runs. An alert will be sent to Slack before the deletion.

## Script Workflow

- Script will be scheduled to run every day by cron
- Compile list of runs in `/genetics`
- To qualify for automated deletion, each runs need to fulfill four main criterias: 
  - 002 project on DNANexus
  - Runs on `staging52`
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
6. `ANSIBLE_WEEK `: number of week old (e.g. 6)
7. `DNANEXUS_TOKEN `: authentication token for dxpy login
8. `ANSIBLE_PICKLE_PATH`: directory to save memory e.g /log/monitoring/ansible.pickle
9. `ANSIBLE_JIRA_ASSAY`: e.g. TWE,MYE **use comma to include multiple assays**
10. `JIRA_TOKEN`: Jira API token
11. `JIRA_EMAIL`: Jira API email
12. `ANSIBLE_DEBUG`: (optional)
13. `JIRA_URL`: Jira API Rest url
14. `SLACK_NOTIFY_JIRA_URL`: Jira helpdesk queue url (for direct link to Jira sample ticket)
15. `SLACK_TOKEN`: slack auth token

## Logging

Logging function is written in ` helper.py ` with format ` %(asctime)s:%(name)s:%(module)s:%(levelname)s:%(message)s `

E.g. ``` 2021-11-16 14:39:45,173```:```ansible main log```:```main```:```INFO```:```Fetching Dxpy API 211014_A01295_0031_AHL3MFDRXY started ```

Log file (``` ansible-run-monitoring.log ```) will be stored in ``` /log/monitoring/ansible-run-monitoring.log ``` in ansible server

## Automation

Cron has been scheduled to run periodically to check for runs older than X number of months

## Mock Testing

`Dockerfile.test` has been provided.

```
# Build the image
docker build -t ansible:test -f Dockerfile.test .

# Run a mock test
# Require mounting of /log/monitoring for storing memory, /genetics for mock create runs in /genetics directory
docker run --env-file <path to .env file> -v <path to /test/log/monitoring>:/log/monitoring -v <path to /test/genetics>:/genetics ansible:test /bin/bash -c "python -u mock.py && python -u main.py"

# Unit test functions in util.py
docker run --env-file <path to .env file> ansible:test
```
#### Mock Testing Command
`mock.py` will pick a random run from `runs.txt` to create a nested directory in `/genetics`. A log file `run.{name}.lane.all.log` will be generated in `/log/dx-streaming-upload/A01295a`. Running the mock command on the 1st of any month (edit your workspace date/time) should trigger the whole workflow, else the script will stop as there's no runs in its memory (expected). The expected workflow on the 1st should be that the script will recognize the run in `/genetics` and `/log/dx-streaming-upload/A01295a`, thus showing overlap file to be 1. The run will then be stored in `ansible_dict.pickle`. If we change our workspace date/time to any date other than the first and run the mock command, it will send a Slack notification to alert about the deletion. Then we change our workspace date/time back to the 1st and run the mock command, it will proceed to delete the run in `/genetics` and continue searching for overlap between `/genetics` and `/log/dx-streaming-upload/A01295a`

## Error

If there's an error with the auth token for dnanexus, the error code below will be returned\
`" The token could not be found, code 401. Request Time=1637168014.38, Request ID=unavailable "`

For more information regarding the specific of error codes, please visit [here](https://documentation.dnanexus.com/developer/api/protocols).

Any bugs or suggestions for improvement, please raise an issue
