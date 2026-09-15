# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence

"""Async foundation for REST API clients with  retries, rate limiting, and response caching."""

import os
import sys
from ast import literal_eval
from importlib.metadata import PackageNotFoundError, version
from typing import cast

from loguru import logger

try:
    __version__ = version("reqadence")
except PackageNotFoundError:
    __version__ = "0.0.0"


logger.disable("reqadence")

LOG_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<level>{message}</level>"
)


def enable_logging(
    level_set: int,
    stdout_set: bool = True,
    file_path: str | None = None,
    log_format: str = LOG_FORMAT,
    colorize: bool = True,
) -> None:
    r"""Enable logging.

    Args:
        level: Requested log level: `10` is debug, `20` is info.
        file_path: Also write logs to files here.
    """
    handlers: list[dict[str, object]] = []
    if stdout_set:
        handlers.append(
            {
                "sink": sys.stdout,
                "level": level_set,
                "format": log_format,
                "colorize": colorize,
            }
        )
    if isinstance(file_path, str):
        handlers.append(
            {
                "sink": file_path,
                "level": level_set,
                "format": log_format,
                "colorize": colorize,
            }
        )
    _ = logger.configure(handlers=handlers)  # pyright: ignore[reportArgumentType]
    # https://loguru.readthedocs.io/en/stable/api/logger.html#loguru._logger.Logger.configure
    logger.enable("reqadence")


if cast(bool, literal_eval(os.environ.get("REQADENCE_LOG", "False"))):
    level = int(os.environ.get("REQADENCE_LOG_LEVEL") or "20")
    stdout = cast(bool, literal_eval(os.environ.get("REQADENCE_STDOUT") or "True"))
    log_file_path = os.environ.get("REQADENCE_LOG_FILE_PATH")
    enable_logging(level, stdout, log_file_path)
