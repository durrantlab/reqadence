# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence

"""Tests for retry behavior."""

import random

import pytest

from reqadence.api.retry import RetryPolicy


def test_invalid_config_raises():
    """Validate that the RetryPolicy constructor rejects invalid parameters."""
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(initial_backoff=-1.0)
    with pytest.raises(ValueError):
        RetryPolicy(initial_backoff=1.0, max_backoff=0.5)
    with pytest.raises(ValueError):
        RetryPolicy(backoff_factor=0.5)


def test_valid_boundary_values():
    """The exact boundary values are accepted."""
    p = RetryPolicy(
        max_attempts=1, initial_backoff=0.0, max_backoff=0.0, backoff_factor=1.0
    )
    assert p.max_attempts == 1


def test_backoff_ceiling_grows_then_caps():
    """Ceiling is exponential in the attempt number, capped at max_backoff."""
    p = RetryPolicy(initial_backoff=1.0, backoff_factor=2.0, max_backoff=30.0)
    assert p._backoff_ceiling(1) == 1.0
    assert p._backoff_ceiling(2) == 2.0
    assert p._backoff_ceiling(3) == 4.0
    assert p._backoff_ceiling(5) == 16.0
    assert p._backoff_ceiling(6) == 30.0
    assert p._backoff_ceiling(10) == 30.0


@pytest.mark.parametrize("attempt", [1, 2, 3, 4, 5])
def test_backoff_delay_within_full_jitter_range(attempt):
    """Full jitter keeps the delay in [0, ceiling(attempt)]."""
    p = RetryPolicy(random_gen=random.Random(0))
    delay = p.backoff_delay(attempt)
    assert 0.0 <= delay <= p._backoff_ceiling(attempt)


def test_backoff_delay_seed():
    """Two policies sharing a seed produce identical delay sequences."""
    a = RetryPolicy(random_gen=random.Random(1234))
    b = RetryPolicy(random_gen=random.Random(1234))
    assert [a.backoff_delay(i) for i in range(1, 6)] == [
        b.backoff_delay(i) for i in range(1, 6)
    ]
