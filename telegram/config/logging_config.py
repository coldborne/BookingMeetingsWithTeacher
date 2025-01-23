import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Логирование в консоль
    ],
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
