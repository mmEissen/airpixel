import logging.config

import yaml


def load(filename: str) -> None:
    with open(filename) as file_:
        config = yaml.safe_load(file_).get("logging")
    if config is None:
        return
    logging.config.dictConfig(config)
