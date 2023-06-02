# syntax=docker/dockerfile:1

FROM python:3.8-slim

WORKDIR /

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . /

ENTRYPOINT [ "python", "main.py"]