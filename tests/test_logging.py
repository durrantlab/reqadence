# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence

"""Tests for the logging environment variables read at import time."""

import pytest

from reqadence import _env_flag, _env_level


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("True", True),
        (" YES ", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("False", False),
        ("no", False),
        ("off", False),
    ],
)
def test_env_flag_parses_common_spellings(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("REQADENCE_TEST_FLAG", value)
    assert _env_flag("REQADENCE_TEST_FLAG", default=not expected) is expected


@pytest.mark.parametrize("default", [True, False])
def test_env_flag_unset_or_blank_uses_default(
    monkeypatch: pytest.MonkeyPatch, default: bool
) -> None:
    monkeypatch.delenv("REQADENCE_TEST_FLAG", raising=False)
    assert _env_flag("REQADENCE_TEST_FLAG", default=default) is default
    monkeypatch.setenv("REQADENCE_TEST_FLAG", "  ")
    assert _env_flag("REQADENCE_TEST_FLAG", default=default) is default


@pytest.mark.parametrize(
    ("value", "expected"),
    [("10", 10), ("debug", "DEBUG"), (" INFO ", "INFO"), ("", 20)],
)
def test_env_level_accepts_numbers_and_names(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: int | str
) -> None:
    monkeypatch.setenv("REQADENCE_TEST_LEVEL", value)
    assert _env_level("REQADENCE_TEST_LEVEL", default=20) == expected
