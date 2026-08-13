# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence

"""Tests for caching policies and their integration with BaseAPI."""

import asyncio

import httpx
import pytest
from hishel import FilterPolicy, SpecificationPolicy

from reqadence.api.base import BaseAPI
from reqadence.api.cache import AlwaysCachePolicy, CachePolicy, RFCCachePolicy


def _counting_origin(counter: dict[str, int]):
    """Mock origin that returns a fresh response each time,
    counting how many times it was called."""

    def handler(_request: httpx.Request) -> httpx.Response:
        counter["n"] += 1
        return httpx.Response(200, json={"call": counter["n"]})

    return handler


def test_classes_built():
    """Cache policy classes instantiate (except the ABC) and build the right hishel policies."""
    with pytest.raises(TypeError):
        CachePolicy()  # type: ignore[abstract]
    assert isinstance(RFCCachePolicy()._build_hishel_policy(), SpecificationPolicy)
    assert isinstance(AlwaysCachePolicy()._build_hishel_policy(), FilterPolicy)


async def test_build_client_factory(tmp_path):
    """Test that the client factory builds an AsyncClient with caching enabled."""
    factory = RFCCachePolicy(database_path=str(tmp_path / "c.db")).build_client_factory(
        next_transport=httpx.MockTransport(lambda r: httpx.Response(200))
    )
    client = factory(base_url="https://example.test")
    try:
        assert isinstance(client, httpx.AsyncClient)
    finally:
        await client.aclose()


async def test_always_policy_caches_repeat_get(tmp_path):
    """Test that AlwaysCachePolicy caches a second identical GET."""
    counter = {"n": 0}
    factory = AlwaysCachePolicy(
        database_path=str(tmp_path / "c.db")
    ).build_client_factory(
        next_transport=httpx.MockTransport(_counting_origin(counter))
    )
    async with BaseAPI("https://example.test", client_factory=factory) as api:
        a = await api._get_json("entry/6OAV")
        b = await api._get_json("entry/6OAV")
    assert counter["n"] == 1
    assert a == b == {"call": 1}


async def test_rfc_policy_does_not_cache_without_headers(tmp_path):
    """Test that RFC 9111 caching does not cache a second identical GET if the response has no cache headers."""
    counter = {"n": 0}
    factory = RFCCachePolicy(database_path=str(tmp_path / "c.db")).build_client_factory(
        next_transport=httpx.MockTransport(_counting_origin(counter))
    )
    async with BaseAPI("https://example.test", client_factory=factory) as api:
        await api._get_json("entry/6OAV")
        await api._get_json("entry/6OAV")
    assert counter["n"] == 2


async def test_always_policy_respects_ttl(tmp_path):
    """Test that AlwaysCachePolicy respects the TTL and expires cached responses after the specified time."""
    counter = {"n": 0}
    factory = AlwaysCachePolicy(
        default_ttl=1, database_path=str(tmp_path / "c.db")
    ).build_client_factory(
        next_transport=httpx.MockTransport(_counting_origin(counter))
    )
    async with BaseAPI("https://example.test", client_factory=factory) as api:
        await api._get_json("entry/6OAV")
        assert counter["n"] == 1
        await asyncio.sleep(1.5)
        await api._get_json("entry/6OAV")
    assert counter["n"] == 2
