# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence

"""Async foundation for REST API clients with retries, rate limiting, and response caching."""

import os
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import HandlerConfig

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
    level_set: int | str,
    stdout_set: bool = True,
    file_path: str | None = None,
    log_format: str = LOG_FORMAT,
    colorize: bool = True,
) -> None:
    """Enable reqadence's log output.

    This replaces any handlers already configured on loguru's global logger.

    Args:
        level_set: Minimum level to log, as a number (`10` is debug, `20` is
            info) or a loguru level name such as `"DEBUG"`.
        stdout_set: Whether to log to standard output.
        file_path: If given, also write logs to this file.
        log_format: loguru format string applied to each record.
        colorize: Whether to add ANSI color codes to the output.
    """
    handlers: list[HandlerConfig] = []
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
    logger.configure(handlers=handlers)
    # https://loguru.readthedocs.io/en/stable/api/logger.html#loguru._logger.Logger.configure
    logger.enable("reqadence")


def _env_flag(name: str, default: bool) -> bool:
    """Read a boolean environment variable such as `1`, `true`, or `no`."""
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_level(name: str, default: int) -> int | str:
    """Read a log level given as a number (`10`) or a name (`DEBUG`)."""
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    return int(value) if value.isdigit() else value.upper()


if _env_flag("REQADENCE_LOG", default=False):
    enable_logging(
        _env_level("REQADENCE_LOG_LEVEL", default=20),
        _env_flag("REQADENCE_STDOUT", default=True),
        os.environ.get("REQADENCE_LOG_FILE_PATH"),
    )
