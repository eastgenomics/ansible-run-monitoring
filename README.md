# Ansible Run Monitoring

Python script to report old runs in '/genetics' on ansible server by sending email to helpdesk.

## Script Workflow

- Get all runs in `genetics` directory and `log` directory (`/var/log/dx-streaming-upload`) in ansible server
- Compare runs in both directory for overlap (runs which have log in log directory)
- Each runs need to fulfill two main criterias to be considered: (a) 002 project is created on DNANexus (b) run folder exist in Staging52
- Compile all run which check both criteria and send an email to helpdesk with attachment (a text file of their respective directory path e.g. ` /genetics/A01295/ABC_RUNS`
- DataFrame Table will also be in the email (example below)

Project  | Created | Data Usage | Created By | Age (Week) | Uploaded to Staging52 | Old Enough | 002 Directory Found
------------- | ------------- | ------------- | ------------- | ------------- | ------------- | ------------- | ------------- | 
211115_A01295_0035_AHMYGGDRXY  | 2021-10-18 | 533.0 GB | user-aishadahir | 30 | True | True | True


## Rebuilding Docker Image

Contains the Dockerfile and requirement.txt for re-building the docker image.

Run ```docker build -t <image name> .``` 

## Packages Installed
1. dxpy
2. tabulate
3. pandas
4. dotenv (only for development purpose)

Docker base image: python3.8-slim-buster \
**Tested on Ubuntu 20.04.3 LTS**


## Running the Container

Run Command: ` docker run --env-file <env file> -v /genetics:/var/genetics -v /var/log:/var/log <docker image> `

Running the container requires mounting of two directories from local filesystem ` /genetics ` and ` /var/log ` to the docker container. This allows the docker container to read files in /genetic in ansible server and write (log) into the local filesystem.

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
10. ` ANSIBLE_WEEK `: number of week old (e.g. 6)
11. ` DNANEXUS_TOKEN `: authentication token for dxpy login

## Logging

Logging function is written in ` helper.py ` with format ` %(asctime)s:%(name)s:%(module)s:%(levelname)s:%(message)s `

E.g. ``` 2021-11-16 14:39:45,173```:```ansible main log```:```main```:```INFO```:```Fetching Dxpy API 211014_A01295_0031_AHL3MFDRXY started ```

Log file (``` ansible-run-monitoring.log ```) will be stored in ``` /var/log/monitoring ``` in ansible server

## Automation

Cron has been set to run monthly to check for runs older than X number of months

## Error

If there's an error with the auth token for dnanexus, the error code below will be returned\
`" The token could not be found, code 401. Request Time=1637168014.38, Request ID=unavailable "`

For more information regarding the specific of error codes, please visit [here](https://documentation.dnanexus.com/developer/api/protocols).

Any bugs or suggestions for improvement, please raise an issue
