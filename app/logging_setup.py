from __future__ import annotations

import logging
import sys

from app.config import AppConfig


def setup_logging(config: AppConfig) -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
