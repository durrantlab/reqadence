# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence


"""
Implementation for HTTP response caching policies allowing for flexible caching
strategies in API clients.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from hishel import (
    AsyncSqliteStorage,
    BaseFilter,
    CacheOptions,
    FilterPolicy,
    Request,
    Response,
    SpecificationPolicy,
)
from hishel.httpx import AsyncCacheTransport


@dataclass(slots=True, frozen=True)
class CachePolicy(ABC):
    """Configuration for HTTP response caching."""

    default_ttl: int | None = 3600
    """Default time-to-live (TTL) in seconds for cached responses. 
        Default is 3600 sec (i.e., 1 hr)"""

    supported_methods: frozenset[str] = frozenset({"GET", "HEAD"})
    """HTTP methods that are eligible for caching. Default is GET and HEAD."""

    database_path: str = ".cache/hishel/hishel_cache.db"
    """Path to the SQLite database file used for caching.
    Default is .cache/hishel/hishel_cache.db"""

    @abstractmethod
    def _build_hishel_policy(self) -> Any:
        """Return the hishel policy object for this strategy."""
        raise NotImplementedError()

    def build_client_factory(
        self, next_transport: httpx.AsyncBaseTransport | None = None
    ) -> Callable[..., httpx.AsyncClient]:
        """Build the caching transport for the API client.

        Args:
            next_transport: The underlying transport to use for cache misses.
                If None, defaults to `httpx.AsyncHTTPTransport()`.

        Returns:
            A factory accepting the same keyword arguments as `httpx.AsyncClient`
                but with caching enabled according to the specified `CachePolicy`.
        """

        cache_policy = self._build_hishel_policy()
        storage = AsyncSqliteStorage(
            database_path=self.database_path,
            default_ttl=self.default_ttl,
        )

        def factory(**kwargs: Any) -> httpx.AsyncClient:
            transport = AsyncCacheTransport(
                next_transport=next_transport or httpx.AsyncHTTPTransport(),
                storage=storage,
                policy=cache_policy,
            )
            return httpx.AsyncClient(transport=transport, **kwargs)

        return factory


@dataclass(slots=True, frozen=True)
class RFCCachePolicy(CachePolicy):
    """RFC 9111 caching where it follows the response's cache headers.
    Caches nothing when the server sends no cache headers.

    Use for APIs that send proper cache headers.
    """

    def _build_hishel_policy(self) -> Any:

        return SpecificationPolicy(
            cache_options=CacheOptions(supported_methods=list(self.supported_methods))
        )


@dataclass(slots=True, frozen=True)
class AlwaysCachePolicy(CachePolicy):
    """Force-cache by method & status, ignoring cache headers."""

    cacheable_status_codes: frozenset[int] = frozenset({200})

    def _build_hishel_policy(self) -> Any:

        methods = frozenset(m.upper() for m in self.supported_methods)
        codes = frozenset(self.cacheable_status_codes)

        class _MethodFilter(BaseFilter[Request]):
            def needs_body(self) -> bool:
                """This filter does not require the request body."""
                return False

            def apply(self, item: Request, body: bytes | None) -> bool:
                """Cache only if the HTTP method is in the supported methods set."""
                return item.method.upper() in methods

        class _StatusFilter(BaseFilter[Response]):
            def needs_body(self) -> bool:
                """This filter does not require the response body."""
                return False

            def apply(self, item: Response, body: bytes | None) -> bool:
                """
                Cache only if the HTTP status code is in the cacheable
                status codes set.
                """
                return item.status_code in codes

        return FilterPolicy(
            request_filters=[_MethodFilter()],
            response_filters=[_StatusFilter()],
        )
