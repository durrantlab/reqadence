# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence

"""Tests for error classes"""

import pytest

from reqadence.api.errors import APIError, PermanentAPIError, TransientAPIError


def test_message_includes_status_when_present():
    """If a status code is provided, it is included in the error message."""
    err = APIError("https://x/y", status_code=404)
    assert err.url == "https://x/y"
    assert err.status_code == 404
    assert "404" in str(err)
    assert "https://x/y" in str(err)


def test_message_wo_status():
    """If no status code is provided, the message is just the URL."""
    err = APIError("https://x/y")
    assert err.status_code is None
    assert str(err) == "https://x/y"


@pytest.mark.parametrize("cls", [PermanentAPIError, TransientAPIError])
def test_subclasses_are_catchable_as_api_error(cls):
    """Both concrete errors inherit from APIError and carry its attributes."""
    err = cls("https://x", status_code=500)
    assert isinstance(err, APIError)
    assert err.status_code == 500
    with pytest.raises(APIError):
        raise err
