# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence

import os

import pytest

from reqadence import enable_logging

TEST_DIR = os.path.dirname(__file__)


@pytest.fixture(scope="session", autouse=True)
def turn_on_logging():
    enable_logging(10)


@pytest.fixture
def sleep_recorder():
    """An async ``sleep`` function that records the delays it was called with."""

    class _Recorder:
        def __init__(self) -> None:
            self.calls: list[float] = []

        async def __call__(self, delay: float) -> None:
            self.calls.append(delay)

    return _Recorder()
