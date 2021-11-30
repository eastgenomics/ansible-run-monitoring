#!/bin/sh

cd ~
docker run --env-file config.txt -v /genetics:/var/genetics -v /var/log:/var/log ansible