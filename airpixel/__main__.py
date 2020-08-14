from __future__ import annotations

import asyncio
import dataclasses
import logging
import typing as t

import yaml

from airpixel import framework, monitoring, logging_config


log = logging.getLogger("airpixel")


@dataclasses.dataclass
class Config:
    framework_config: framework.Config
    monitoring_config: monitoring.Config

    @classmethod
    def from_dict(cls, dict_: t.Dict[str, t.Any]) -> Config:
        return cls(
            framework.Config.from_dict(dict_["framework"]),
            monitoring.Config.from_dict(dict_["monitoring"]),
        )

    @classmethod
    def load(cls, file_name: str) -> Config:
        with open(file_name) as file_:
            return cls.from_dict(yaml.safe_load(file_))


async def main() -> None:
    logging_config.load("airpixel.yaml")
    config = Config.load("airpixel.yaml")
    framework_app = framework.Application(config.framework_config)
    monitoring_app = monitoring.Application(config.monitoring_config)
    try:
        await asyncio.gather(framework_app.run_forever(), monitoring_app.run_forever())
    except KeyboardInterrupt:
        log.info("Application shut down by user (keyboard interrupt)")


asyncio.run(main())
