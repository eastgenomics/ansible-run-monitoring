# syntax=docker/dockerfile:1

FROM python:2.7-slim-buster

WORKDIR /

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY main.py .env /

ENV HTTP_PROXY="http://proxy.net.addenbrookes.nhs.uk:8080"
ENV HTTPS_PROXY="https://proxy.net.addenbrookes.nhs.uk:8080"

CMD [ "python", "main.py"]