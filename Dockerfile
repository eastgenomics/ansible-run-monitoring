# syntax=docker/dockerfile:1

FROM python:3.8-slim

RUN apt-get -y update && apt-get -y upgrade -y && apt-get -y install gcc

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . /app

ENTRYPOINT [ "python", "main.py"]