# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence

"""Tests for API base class and helpers."""

import random
from dataclasses import FrozenInstanceError

import httpx
import pytest

from reqadence.api.base import (
    DEFAULT_RATE_PER_SECOND,
    APIResponseType,
    BaseAPI,
    ClientConfig,
    _Action,
)
from reqadence.api.errors import PermanentAPIError, TransientAPIError
from reqadence.api.retry import RetryPolicy

_BASE_URL = "https://example.test"


class _CountingHandler:
    """A MockTransport handler that counts how many times it was called."""

    def __init__(self, respond) -> None:
        self.calls = {"n": 0}
        self._respond = respond

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls["n"] += 1
        return self._respond(self.calls["n"], request)


def _fail_then_succeed(
    fail_times: int, status: int = 429, *, headers=None
) -> _CountingHandler:
    """Return `status` for the first `fail_times` calls, then 200."""

    def respond(n: int, _request: httpx.Request) -> httpx.Response:
        if n <= fail_times:
            return httpx.Response(status, headers=headers)
        return httpx.Response(200, json={"ok": True})

    return _CountingHandler(respond)


def _raise_connect_error() -> _CountingHandler:
    """Handler that always raises a transport error and counts the calls."""

    def respond(n: int, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("booo", request=request)

    return _CountingHandler(respond)


def _mock_factory(handler):
    """A client_factory that routes every request through `handler`."""

    def factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


def _det_config(**retry_overrides) -> ClientConfig:
    """ClientConfig whose retry policy uses a seeded RNG for reproducible jitter."""
    return ClientConfig(
        retry_policy=RetryPolicy(random_gen=random.Random(0), **retry_overrides)
    )


def _api(handler=None, *, config=None, sleep=None) -> BaseAPI:
    """Build a BaseAPI over a mock transport routing every request to `handler`.
    If `sleep` is provided, it is called instead of `asyncio.sleep` to record the sleep times.
    """
    extra = {"sleep": sleep} if sleep is not None else {}
    return BaseAPI(
        _BASE_URL,
        config=config,
        client_factory=_mock_factory(handler or (lambda request: httpx.Response(200))),
        **extra,
    )


def _bare(config=None) -> BaseAPI:
    """A BaseAPI on a trivial 200 handler, for pure-helper assertions."""
    return _api(config=config)


def _client(handler, sleep, **retry_overrides) -> BaseAPI:
    """A BaseAPI driven by a scripted handler with seeded jitter and recording sleep."""
    return _api(handler, config=_det_config(**retry_overrides), sleep=sleep)


def test_client_config_defaults():
    """Test that ClientConfig has the expected default values."""
    cfg = ClientConfig()
    assert cfg.response_format is APIResponseType.JSON
    assert cfg.timeout == 30.0
    assert isinstance(cfg.retry_policy, RetryPolicy)
    assert cfg.headers is None


@pytest.mark.parametrize("bad", [0, -1, -0.5])
def test_client_config_rejects_nonpositive_timeout(bad):
    """Test that ClientConfig raises ValueError for non-positive timeout values."""
    with pytest.raises(ValueError):
        ClientConfig(timeout=bad)


def test_client_config_is_frozen():
    """Test that ClientConfig is frozen and cannot be modified after creation."""
    cfg = ClientConfig()
    with pytest.raises(FrozenInstanceError):
        cfg.timeout = 10  # type: ignore[misc]


def test_defaults():
    """Test that the constants and enums have the expected values."""
    assert APIResponseType.JSON == "json"
    assert APIResponseType.XML == "xml"
    assert DEFAULT_RATE_PER_SECOND == 5.0


@pytest.mark.parametrize(
    "given, expected",
    [
        ("https://x.com", "https://x.com/"),
        ("https://x.com/", "https://x.com/"),
        ("https://x.com/api", "https://x.com/api/"),
        ("https://x.com/api/", "https://x.com/api/"),
    ],
)
async def test_base_url_is_normalized(given, expected):
    """Test that BaseAPI normalizes the base_url to always end with a slash."""
    async with BaseAPI(
        given, client_factory=_mock_factory(lambda r: httpx.Response(200))
    ) as api:
        assert api.base_url == expected


async def test_defaults_created_when_none():
    """Test that BaseAPI creates default config and rate limiter when not provided."""
    async with _bare() as api:
        assert isinstance(api.config, ClientConfig)
        assert api.rate_limiter is not None


async def test_default_headers():
    """Test that BaseAPI returns the correct default Accept header based on config."""
    async with _bare(ClientConfig(response_format=APIResponseType.JSON)) as api:
        assert api._default_headers()["accept"] == "application/json"
    async with _bare(ClientConfig(response_format=APIResponseType.XML)) as api:
        assert api._default_headers()["accept"] == "application/xml"


async def test_default_headers_merge():
    """Test that BaseAPI merges user-specified headers with the default headers and override them if they conflict."""
    cfg = ClientConfig(headers={"user-agent": "reqadence/1.0", "accept": "text/plain"})
    async with _bare(cfg) as api:
        h = api._default_headers()
        assert h["user-agent"] == "reqadence/1.0"
        # The user-specified header override the default Accept header.
        assert h["accept"] == "text/plain"


_CLASSIFY_CASES = {
    200: _Action.RETURN,
    302: _Action.RETURN,
    400: _Action.FAIL,
    404: _Action.FAIL,
    429: _Action.RETRY,
    500: _Action.RETRY,
    503: _Action.RETRY,
}


@pytest.mark.parametrize("status, expected", _CLASSIFY_CASES.items())
async def test_classify(status, expected):
    """Test that BaseAPI classifies HTTP status codes into the correct _Action enum."""
    async with _bare() as api:
        assert api._classify(httpx.Response(status)) == expected


async def test_retry_delay():
    """Test that BaseAPI uses the Retry-After header to determine the retry delay if present."""
    async with _bare() as api:
        resp = httpx.Response(503, headers={"retry-after": "2.5"})
        assert api._retry_delay(resp, attempt=1) == 2.5


async def test_retry_delay_falls_back_to_backoff(sleep_recorder):
    """Test that BaseAPI falls back to the retry policy's backoff delay if Retry-After header is invalid or missing."""
    cfg = ClientConfig(retry_policy=RetryPolicy(random_gen=random.Random(42)))
    mirror = RetryPolicy(random_gen=random.Random(42))

    async with _bare(cfg) as api:
        invalid = httpx.Response(503, headers={"retry-after": "soon"})
        assert api._retry_delay(invalid, attempt=1) == mirror.backoff_delay(1)

        assert api._retry_delay(None, attempt=2) == mirror.backoff_delay(2)


async def test_success_return(sleep_recorder):
    """Test that BaseAPI._get returns successfully on the first attempt without retries."""
    handler = _fail_then_succeed(0)
    async with _client(handler, sleep_recorder) as api:
        resp = await api._get("thing")
    assert resp.status_code == 200
    assert handler.calls["n"] == 1
    assert sleep_recorder.calls == []


async def test_retries_transient_then_succeeds(sleep_recorder):
    """Test that BaseAPI._get retries on transient errors and eventually succeeds."""
    handler = _fail_then_succeed(1, 429)
    async with _client(handler, sleep_recorder) as api:
        resp = await api._get("thing")
    assert resp.status_code == 200
    assert handler.calls["n"] == 2
    assert len(sleep_recorder.calls) == 1


async def test_retry_after_header_drives_delay(sleep_recorder):
    """Test that BaseAPI._get respects the Retry-After header for retry delays."""
    handler = _fail_then_succeed(1, 503, headers={"retry-after": "0"})
    async with _client(handler, sleep_recorder) as api:
        await api._get("thing")
    assert sleep_recorder.calls == [0.0]


async def test_exhausts_retries(sleep_recorder):
    """Test that BaseAPI._get exhausts retryable errors and raises a TransientAPIError."""
    handler = _fail_then_succeed(99, 503)
    with pytest.raises(TransientAPIError) as exc:
        async with _client(handler, sleep_recorder, max_attempts=3) as api:
            await api._get("thing")
    assert handler.calls["n"] == 3
    assert len(sleep_recorder.calls) == 2
    assert exc.value.status_code == 503


async def test_transport_error(sleep_recorder):
    """Test that BaseAPI._get raises a TransientAPIError on transport errors and respects max_attempts."""
    handler = _raise_connect_error()
    with pytest.raises(TransientAPIError) as exc:
        async with _client(handler, sleep_recorder, max_attempts=3) as api:
            await api._get("thing")
    assert handler.calls["n"] == 3
    assert exc.value.status_code is None


async def test_permanent_status_raises_immediately(sleep_recorder):
    """Test that BaseAPI._get raises a PermanentAPIError immediately on non-retryable status codes ignoring retries."""
    handler = _fail_then_succeed(99, 404)
    with pytest.raises(PermanentAPIError) as exc:
        async with _client(handler, sleep_recorder) as api:
            await api._get("thing")
    assert handler.calls["n"] == 1
    assert sleep_recorder.calls == []
    assert exc.value.status_code == 404


async def test_post_format(sleep_recorder):
    """Test that BaseAPI._post sends the correct method and JSON body."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    async with _client(handler, sleep_recorder) as api:
        await api._post("thing", json={"a": 1})
    assert seen["method"] == "POST"
    assert b"a" in seen["body"]


async def test_get_json_parse(sleep_recorder):
    """Test that BaseAPI._get_json parses the JSON body of the response."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"k": "v"})

    async with _client(handler, sleep_recorder) as api:
        assert await api._get_json("thing") == {"k": "v"}


async def test_get_json_returns_none(sleep_recorder):
    """Test that BaseAPI._get_json returns None when the response is invalid JSON."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    async with _client(handler, sleep_recorder) as api:
        assert await api._get_json("thing") is None


async def test_context_manager_enters_self_and_closes():
    api = _bare()
    assert api._client.is_closed is False
    async with api as entered:
        assert entered is api
        assert api._client.is_closed is False
    assert api._client.is_closed is True
