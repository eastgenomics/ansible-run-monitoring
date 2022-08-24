# Ansible Run Monitoring

Python script to report deletable runs in `/genetics` on ansible server by sending email to helpdesk & automate deletion of stale run

## Script Workflow

- Get all runs in `genetics` directory and `log` directory (`/var/log/dx-streaming-upload`) in ansible server
- Compare runs in both directory for overlap (runs which have log in log directory - meaning it has been uploaded to DNANexus)
- To qualify for automated deletion, each runs need to fulfill four main criterias: 
  - 002 project of run created on DNANexus 
  - Run folder exist in `staging52`
  - 002 project has been created for more than `ANSIBLE_WEEK`
  - have Jira ticket with status `ALL SAMPLES RELEASED`
  - have assay option in `ANSIBLE_JIRA_ASSAY`
- Compile all qualified runs & save it in memory (pickle)
- Send email to helpdesk on other unqualified runs e.g. runs without `ALL SAMPLES RELEASED` Jira status or 002 project hasn't been created for long enough
- Send Slack reminder on qualified runs
- Delete qualified runs in the next run (e.g. 1st of next month)

## Rebuilding Docker Image

Run `docker build -t <image name> .`

## Running the Container
```
docker run --env-file <path to config> -v /genetics:/genetics -v /var/log/dx-streaming-upload:/log/dx-streaming-upload -v /var/log/monitoring:/log/monitoring <image name:tag>
```

## Config Env Variables

1. `ANSIBLE_GENETICDIR`: the directory to look into for original genetic run. **This should be directory in docker container**
2. `ANSIBLE_LOGSDIR`: the directory to look into for uploaded run logs **This should be directory in docker container**
3. `ANSIBLE_SENDER`: the 'from' for email function (e.g. BioinformaticsTeamGeneticsLab@addenbrookes.nhs.uk)
4. `ANSIBLE_RECEIVERS`: the 'send to' for email function, **use comma to include multiple emails** (e.g. abc@email.com, bbc@email.com)
5. `ANSIBLE_SERVER`: server host (str) for SMTP email function
6. `ANSIBLE_PORT`: port number for SMTP email function
7. `ANSIBLE_SEQ`: sequencing machine, **use comma to include more machines** (e.g. a01295, a01303, a1405)
8. `HTTP_PROXY`: http proxy
9. `HTTPS_PROXY`: https proxy
10. `ANSIBLE_WEEK `: number of week old (e.g. 6)
11. `DNANEXUS_TOKEN `: authentication token for dxpy login
12. `ANSIBLE_PICKLE_PATH`: directory to save memory e.g /log/monitoring/ansible.pickle
13. `ANSIBLE_JIRA_ASSAY`: e.g. TWE,MYE **use comma to include multiple assays**
14. `JIRA_TOKEN`: Jira API token
15. `JIRA_EMAIL`: Jira API email
16. `ANSIBLE_DEBUG`: (optional)
17. `JIRA_URL`: Jira API Rest url
18. `SLACK_NOTIFY_JIRA_URL`: Jira helpdesk queue url (for direct link to Jira sample ticket)
19. `SLACK_TOKEN`: slack auth token

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
