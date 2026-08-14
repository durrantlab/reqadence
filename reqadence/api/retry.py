# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence


"""Retry configuration for asynchronous API requests."""

import random
from dataclasses import dataclass, field


@dataclass(slots=True)
class RetryPolicy:
    """Configuration for retrying API requests on transient errors."""

    max_attempts: int = 5

    """Maximum number of retry attempts, including the initial request. Must be >= 1"""

    initial_backoff: float = 1.0

    """Initial delay time in seconds before the first retry attempt. Must be >= 0.0"""

    max_backoff: float = 30.0

    """Upper limit for delay time in seconds on any single retry attempt."""

    backoff_factor: float = 2.0

    """Multiplier factor applied to the backoff with each consecutive attempt. Must be >= 1.0."""

    retryable_status_codes: frozenset[int] = frozenset({429, 500, 502, 503, 504})

    """HTTP status codes that should trigger a retry instead of returning immediate failure."""

    random_gen: random.Random = field(
        default_factory=random.Random, repr=False, compare=False
    )

    """Source of randomness for jitter. Seed it for deterministic retries."""

    def __post_init__(self) -> None:
        """Validate the retry policy fields after initialization.

        Raises:
            ValueError: If any field has an invalid value.
        """
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {self.max_attempts}")
        if self.initial_backoff < 0.0:
            raise ValueError(
                f"initial_backoff must be >= 0.0, got {self.initial_backoff}"
            )
        if self.max_backoff < self.initial_backoff:
            raise ValueError(
                f"max_backoff must be >= initial_backoff, got {self.max_backoff}"
            )
        if self.backoff_factor < 1.0:
            raise ValueError(
                f"backoff_factor must be >= 1.0, got {self.backoff_factor}"
            )

    def _backoff_ceiling(self, attempt: int) -> float:
        """Calculate the deterministic backoff ceiling for a given retry attempt.

        Args:
            attempt: Current retry attempt number (1-based).

        Return:
            The capped exponential time in seconds for the given attempt.
        """
        return min(
            self.max_backoff,
            self.initial_backoff * (self.backoff_factor ** (attempt - 1)),
        )

    def backoff_delay(self, attempt: int) -> float:
        """Return the total backoff delay for a given retry attempt using full jitter

        Args:
            attempt: Current retry attempt number (1-based).

        Returns:
            A jittered delay value in seconds between 0 and the capped exponential
                backoff for the given attempt.
        """
        return self.random_gen.uniform(0, self._backoff_ceiling(attempt))
