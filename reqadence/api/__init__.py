# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence
"""Initialize the API package."""

from .base import (
    DEFAULT_RATE_PER_SECOND,
    APIResponseType,
    BaseAPI,
    ClientConfig,
    JSONValue,
    QueryParams,
)
from .cache import AlwaysCachePolicy, CachePolicy, RFCCachePolicy
from .errors import APIError, PermanentAPIError, TransientAPIError
from .retry import RetryPolicy

__all__: list[str] = [
    "BaseAPI",
    "RetryPolicy",
    "ClientConfig",
    "DEFAULT_RATE_PER_SECOND",
    "APIResponseType",
    "CachePolicy",
    "RFCCachePolicy",
    "AlwaysCachePolicy",
    "JSONValue",
    "QueryParams",
    "APIError",
    "PermanentAPIError",
    "TransientAPIError",
]
