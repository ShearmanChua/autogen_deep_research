"""
This module implements logger configuration and creation methods.
"""

import logging
import logging.config
from pathlib import Path

import yaml

LOGGER_FORMAT = "%(asctime)s:%(levelname)s:%(filename)s:%(lineno)s -- %(message)s"

DEFAULT_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": LOGGER_FORMAT}},
    "handlers": {
        "console": {
            "formatter": "simple",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "level": "DEBUG",
        },
        "file": {
            "backupCount": 5,
            "encoding": "utf8",
            "level": "DEBUG",
            "filename": "log/agents.log",
            "mode": "w",
            "formatter": "simple",
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 1048576,
        },
    },
    "loggers": {
        "agents.production": {
            "level": "INFO",
            "propagate": False,
            "handlers": ["console"],
        }
    },
    "root": {"level": "WARN", "handlers": ["console"]},
}


def setup_logger() -> None:
    """
    Configure the root logger for logging in the application.
    """

    Path(Path.cwd(), "log").mkdir(exist_ok=True)

    try:
        config_file = Path("./logging_config.yaml").absolute()
        with open(file=config_file, mode="rt", encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file.read())
    except FileNotFoundError:
        config = DEFAULT_CONFIG

    # Configure the logging module with the config file
    logging.config.dictConfig(config)


def get_logger(name: str = "agents.production") -> logging.Logger:
    """
    Returns a logger object for the Agents library.

    Args:
        name (str): Name of the logger to be fetched

    Returns:
        logging.Logger: The logger object for the Agents library.
    """
    return logging.getLogger(name)
