# Ansible Run Monitoring

Ansible-Run-Monitoring is a python script to report successfully-uploaded runs on ansible server mounted volume ```/genetics```


## Script

Script will get all the run names in ``` /genetics ``` and compare it with the logs folder in ``` /var/log/dx-streaming-upload ```. It gets the overlap between these two directories and check if the run ```(002_<run name>_ABC)``` exist on DNANexus. Runs which exist on DNANexus are compiled into a table in email and a txt file is generated with their respective directory pathways e.g. ``` /genetics/A01295/ABC_RUNS & /var/log/dx-streaming-upload/A01295/log.ABC_RUNS ```


## Rebuilding Docker Image

Contains the Dockerfile for building the image and deployment. Run ```docker build -t <image name> .``` 

Tested on Ubuntu 20.04.3 LTS<br>


## Running the Container

Run Command: ``` docker run --env-file <environment filename> -v <local genetic dir>:<docker dir> test ```

Running the container requires mounting of two directories from local filesystem ``` /genetics ``` and ``` /var/log ``` to the docker container


**Current tested command**: ``` docker run --env-file <env.txt> -v /genetics:/var/genetics -v /var/log:/var/log  <image name> ```


## Automation

It is written to run periodically (e.g. every 3 months) to find delete-able runs in ```/genetics``` <br> using crons.

Any bugs or suggestions for improvement, please raise an issue
