# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence


"""
Implementation for base classes allowing for asynchronous API clients with built-in
retry and rate limiting.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from types import TracebackType
from typing import Self

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger

from reqadence.api.errors import PermanentAPIError, TransientAPIError
from reqadence.api.retry import RetryPolicy


class APIResponseType(StrEnum):
    """Expected response format for an API client."""

    JSON = "json"
    XML = "xml"


class _Action(StrEnum):
    """Internal enum for handling http request actions."""

    RETURN = "return"
    RETRY = "retry"
    FAIL = "fail"


DEFAULT_RATE_PER_SECOND: int = 5
"""Default leaky-bucket rate for the asynchronous client limiter, in requests per second."""

type JSONValue = (
    str | int | float | bool | None | dict[str, "JSONValue"] | list["JSONValue"]
)

"""Alias for any value representable in JSON to allow type hinting of JSON responses."""

type QueryParams = dict[str, str | int | float | bool | None]
"""Alias for query parameters to allow type hinting of query parameters in requests."""


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Configuration for a BaseAPI client.

    Raises:
        ValueError: If the timeout is set to a non-positive value.
    """

    response_format: APIResponseType = APIResponseType.JSON
    """Expected response format used to set the Accept header."""

    timeout: float = 30.0
    """Per-request timeout in seconds. Must be > 0."""

    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    """Backoff and retry configuration."""

    headers: dict[str, str] | None = None
    """Extra allowed headers merged over the defaults (e.g. a contact User-Agent
    or Authorization). """

    def __post_init__(self) -> None:
        """Enforce positive per-request timeout after initialization."""
        if self.timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {self.timeout}")


class BaseAPI:
    """Base class for asynchronous REST API calls
    providing request retry, rate limiting, and JSON parsing.
    Meant to be subclassed for specific APIs."""

    def __init__(
        self,
        base_url: str,
        *,
        config: ClientConfig | None = None,
        rate_limiter: AsyncLimiter | None = None,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Initialize the API client.

        Args:
            base_url: Base URL for the API endpoints.
            config: Client configuration.
                Defaults to [ClientConfig][api.base.ClientConfig] if none is provided.
            rate_limiter: AsyncLimiter instance for rate limiting. Defaults to
                [DEFAULT_RATE_PER_SECOND][api.base.DEFAULT_RATE_PER_SECOND] If none is provided.
            client_factory: A callable that returns an `httpx.AsyncClient` instance.
            sleep: A callable for sleeping between retries. Defaults to `asyncio.sleep`.
        """
        self.base_url: str = base_url.rstrip("/") + "/"
        self.config: ClientConfig = config if config is not None else ClientConfig()
        self.rate_limiter: AsyncLimiter = (
            rate_limiter
            if rate_limiter is not None
            else AsyncLimiter(max_rate=DEFAULT_RATE_PER_SECOND, time_period=1)
        )
        self._client: httpx.AsyncClient = client_factory(
            base_url=self.base_url,
            headers=self._default_headers(),
            timeout=self.config.timeout,
            follow_redirects=True,
        )
        self._sleep: Callable[[float], Awaitable[None]] = sleep

    def _default_headers(self) -> dict[str, str]:
        """Return default request headers for the session.
            Sets the Accept header for the configured response format.

        Returns:
            A dict containing at least `accept` set to `application/json` or `application/xml`
                depending on the configured response format.
                Any additional headers provided in the `[ClientConfig][api.base.ClientConfig]
                may overwrite the defaults to add or replace headers
        """
        accept = (
            "application/json"
            if self.config.response_format is APIResponseType.JSON
            else "application/xml"
        )
        headers = {"accept": accept}
        if self.config.headers:
            headers.update(self.config.headers)
        return headers

    def _classify(self, resp: httpx.Response) -> _Action:
        """Classify the action to take based on the HTTP status code."""
        if resp.status_code in self.config.retry_policy.retryable_status_codes:
            return _Action.RETRY
        if resp.is_error:
            return _Action.FAIL
        return _Action.RETURN

    def _retry_delay(self, resp: httpx.Response | None, attempt: int) -> float:
        """Opt in for the Retry-After header if present, otherwise use the backoff delay.

        Args:
            resp: The HTTP response that triggered the retry.
            attempt: The current retry attempt number (1-based).

        Returns:
            The delay in seconds before the next retry attempt.
        """
        if resp is not None and (value := resp.headers.get("retry-after")):
            try:
                return float(value)
            except ValueError:
                logger.warning(
                    "Invalid Retry-After header value: {value}. Falling back to backoff delay.",
                    value=value,
                )
        return self.config.retry_policy.backoff_delay(attempt)

    async def _request(
        self,
        method: str,
        url: str,
        params: QueryParams | None = None,
        json: JSONValue | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with automatic retries on transient errors and rate
        limiting.

        Args:
            method: HTTP verb (GET, POST)
            url: Full request URL.
            params: Query-string parameters.
            json: JSON body (for POST/PUT).

        Returns:
           Successful `httpx.Response` object.

        Raises:
            PermanentAPIError: When a non-retryable HTTP status code is returned.
            TransientAPIError: When all retry attempts are exhausted or a transport error occurs.
        """
        last_exception: Exception | None = None
        last_resp: httpx.Response | None = None
        max_attempts = self.config.retry_policy.max_attempts
        for attempt in range(1, max_attempts + 1):
            try:
                async with self.rate_limiter:
                    resp = await self._client.request(
                        method,
                        url,
                        params=params,
                        json=json,
                    )
            except httpx.RequestError as exc:
                last_exception = exc
                last_resp = None
                logger.error(
                    "Request error for {url} (attempt {n}/{max}): {exc}",
                    url=url,
                    n=attempt,
                    max=max_attempts,
                    exc=exc,
                )
            else:
                last_resp = resp
                match self._classify(resp):
                    case _Action.RETURN:
                        return resp
                    case _Action.FAIL:
                        logger.error(
                            "Request failed for {url} with HTTP {code}.",
                            url=url,
                            code=resp.status_code,
                        )
                        raise PermanentAPIError(url=url, status_code=resp.status_code)
                    case _Action.RETRY:
                        logger.warning(
                            "Retrying {url} after HTTP {code} ({n}/{max})",
                            url=url,
                            code=resp.status_code,
                            n=attempt,
                            max=max_attempts,
                        )
            if attempt < max_attempts:
                delay = self._retry_delay(last_resp, attempt)
                logger.info("Waiting {delay:.2f} seconds before retrying.", delay=delay)
                await self._sleep(delay)
        tail_msg = f"Last exception: {last_exception}" if last_exception else ""
        logger.error(
            "All {max} attempts failed for {url}. {tail}",
            max=max_attempts,
            url=url,
            tail=tail_msg,
        )
        raise TransientAPIError(
            url=url,
            status_code=last_resp.status_code if last_resp is not None else None,
        )

    async def _get(self, url: str, params: QueryParams | None = None) -> httpx.Response:
        """Shorthand for a GET request."""
        return await self._request("GET", url, params=params)

    async def _post(
        self,
        url: str,
        json: JSONValue | None = None,
        params: QueryParams | None = None,
    ) -> httpx.Response:
        """Shorthand for a POST request."""
        return await self._request("POST", url, json=json, params=params)

    async def _get_json(
        self, url: str, params: QueryParams | None = None
    ) -> JSONValue | None:
        """GET and parse JSON, returning None on failure."""
        resp = await self._get(url, params=params)
        try:
            return resp.json()
        except ValueError:
            logger.error("Failed to parse JSON from {url}", url=url)
            return None

    async def aclose(self) -> None:
        """Close the underlying http client."""
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        """Enter the async context manager and return the client instance."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Ensure the underlying http client is closed when exiting the async context manager."""
        await self.aclose()

    def __repr__(self) -> str:
        """Return the class and base URL for debugging purposes."""
        return f"{self.__class__.__name__}(base_url={self.base_url!r})"
