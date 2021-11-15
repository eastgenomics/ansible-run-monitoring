# syntax=docker/dockerfile:1

FROM python:2.7-slim-buster

WORKDIR /

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY main.py .env util.py /

CMD [ "python", "main.py"]