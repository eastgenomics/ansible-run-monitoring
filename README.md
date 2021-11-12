# Ansible Run Monitoring

Ansible-Run-Monitoring is a simple python script to report duplicates and successfully uploaded runs on ansible server.<br>


## Installation

Contains the Dockerfile for building the image and deployment. Run ```docker build -t <name> .```<br>

Tested on Ubuntu 20.04.3 LTS<br>

## Usage

It is written to run periodically (e.g. every 3 months) to find delete-able runs in ansible server <br>

Any bugs or suggestions for improvement, please raise an issue