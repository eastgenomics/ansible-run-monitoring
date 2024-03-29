"""
main script for logging purpose.
Script can be imported and will generate log file in
directory defined below
"""

import logging
from logging.handlers import TimedRotatingFileHandler
import os
from pathlib import Path
import sys


FORMATTER = logging.Formatter(
    "%(asctime)s:%(name)s:%(module)s:%(levelname)s:%(message)s"
)

if os.access("/log", os.W_OK):
    # running in Docker container
    LOG_FILE = "/log/monitoring/ansible-run-monitoring.log"

    Path("/log/monitoring").mkdir(parents=True, exist_ok=True)
    Path(LOG_FILE).touch(exist_ok=True)
else:
    # running elsewhere (likely testing)
    LOG_FILE = os.path.join(os.getcwd(), "ansible-run-monitoring.log")

    Path(os.getcwd()).mkdir(parents=True, exist_ok=True)
    Path(LOG_FILE).touch(exist_ok=True)


def get_console_handler():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    return console_handler


def get_file_handler():
    file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight")
    file_handler.setFormatter(FORMATTER)
    return file_handler


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(get_console_handler())
    logger.addHandler(get_file_handler())

    logger.propagate = False

    return logger
