# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence


"""Exceptions hierarchical configuration for API requests."""


class APIError(Exception):
    def __init__(self, url: str, status_code: int | None = None) -> None:
        """Base class for API failures, distinguishing retryable errors from permanent ones."""
        self.url = url
        """The URL of the API endpoint."""
        self.status_code = status_code
        """The HTTP status code of the API response, if available."""
        message = f"{url} (HTTP {status_code})" if status_code else url
        super().__init__(message)


class PermanentAPIError(APIError):
    """Non-retryable status: a code not in the [`retry policy's`][api.retry.RetryPolicy.retryable_status_codes] set of status codes."""


class TransientAPIError(APIError):
    """Retries have been exhausted or API transport failed."""
