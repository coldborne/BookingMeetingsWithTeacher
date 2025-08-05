import logging

from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIRECTORY = Path(__file__).resolve().parents[2] / "logs"
LOG_DIRECTORY.mkdir(exist_ok=True)

LOG_FILE = LOG_DIRECTORY / "bot.log"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 10

FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


def __configure_root_logger() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(FORMAT, DATEFMT))
    root.addHandler(console)

    rotating = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    rotating.setFormatter(logging.Formatter(FORMAT, DATEFMT))
    root.addHandler(rotating)


__configure_root_logger()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
