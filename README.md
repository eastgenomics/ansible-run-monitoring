# Ansible Run Monitoring

Ansible-Run-Monitoring is a python script to report successfully-uploaded runs on ansible server mounted volume ```/genetics```.<br>


## Installation

Contains the Dockerfile for building the image and deployment. Run ```docker build -t <name> .```<br>

Tested on Ubuntu 20.04.3 LTS<br>

## Usage

It is written to run periodically (e.g. every 3 months) to find delete-able runs in ```/genetics``` <br>

Any bugs or suggestions for improvement, please raise an issue