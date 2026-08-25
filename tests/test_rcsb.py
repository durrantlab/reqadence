# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence


"""Tests for the RCSB API client and Entry model."""

import os
import random

import httpx
import pytest
import pytest_asyncio

from reqadence.api.base import ClientConfig
from reqadence.api.cache import AlwaysCachePolicy, RFCCachePolicy
from reqadence.api.rcsb import RCSBClient, RCSBEntry
from reqadence.api.retry import RetryPolicy

_ENTRY_6OAV = {
    "rcsb_id": "6OAV",
    "exptl": [{"method": "X-RAY DIFFRACTION"}],
    "rcsb_entry_info": {
        "resolution_combined": [1.939],
        "inter_mol_covalent_bond_count": 0,
        "nonpolymer_entity_count": 1,
    },
    "refine": [{"ls_R_factor_R_work": 0.2001, "ls_R_factor_R_free": 0.236}],
    "pdbx_vrpt_summary_geometry": [{"clashscore": 4.25}],
    "pdbx_vrpt_summary_diffraction": [{"Wilson_B_estimate": 29.663}],
    "rcsb_entry_container_identifiers": {
        "polymer_entity_ids": ["1"],
        "non_polymer_entity_ids": ["2"],
    },
}

_ENTRY_10UJ = {
    "rcsb_id": "10UJ",
    "exptl": [{"method": "ELECTRON MICROSCOPY"}],
    "rcsb_entry_info": {"resolution_combined": [3.9], "nonpolymer_entity_count": 0},
    "pdbx_vrpt_summary_geometry": [{"clashscore": 2.62}],
}


@pytest_asyncio.fixture
async def rcsb():
    """Live RCSB API client, closed on teardown.

    Returns:
        An ``RCSBClient`` instance that is closed when the test finishes.
    """
    async with RCSBClient() as client:
        yield client


@pytest_asyncio.fixture
async def entry_6oav(rcsb) -> RCSBEntry:
    """Pre-fetched 6OAV entry record (6OAV is the reference PDB for these tests).

    Args:
        rcsb: The RCSB client fixture.

    Returns:
        The parsed ``RCSBEntry`` for 6OAV.
    """
    data = await rcsb.get_entry("6OAV")
    assert data is not None, "Failed to fetch 6OAV entry from RCSB."
    return data


@pytest_asyncio.fixture
async def enriched_entry_6oav(rcsb, entry_6oav) -> RCSBEntry:
    """Pre-fetched and enriched 6OAV entry record.

    Args:
        rcsb: The RCSB client fixture.
        entry_6oav: The pre-fetched 6OAV entry record.

    Returns:
        The parsed ``RCSBEntry`` for 6OAV, with enrichment fields filled in.
    """
    data = await rcsb.enrich(entry_6oav)
    assert data is not None, "Failed to enrich 6OAV entry from RCSB."
    return data


def _counting(respond):
    """Wrap a per-call response function; expose invocation count on .calls."""
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        return respond(state["n"], request)

    handler.calls = state
    return handler


def _fail_then_succeed(fail_times: int, status: int = 429, *, headers=None):
    """Mock handler: fail `fail_times` calls with `status`, then 200 + _ENTRY_6OAV.

    Args:
        fail_times: Number of leading calls that return `status`.
        status: Status code returned while failing.
        headers: Optional headers on the failing responses (e.g. Retry-After).
    Returns:
        A handler whose `.calls["n"]` tracks invocation count.
    """

    def respond(n: int, request: httpx.Request) -> httpx.Response:
        if n <= fail_times:
            return httpx.Response(status, headers=headers)
        return httpx.Response(200, json=_ENTRY_6OAV)

    handler = _counting(respond)
    return handler


def _mock_factory(handler):
    """A client_factory routing the real RCSBClient through a mock handler."""

    def factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    return factory


def _det_config(**retry_overrides) -> ClientConfig:
    """ClientConfig with a seeded-RNG retry policy for reproducible jitter."""
    policy = RetryPolicy(random_gen=random.Random(0), **retry_overrides)
    return ClientConfig(retry_policy=policy)


@pytest_asyncio.fixture
async def idle_rcsb():
    """An RCSBClient on a mock transport, closed on teardown.

    For request-free logic like _classify, without leaking a client. The
    transport is never actually reached, so it just returns 200.
    """
    handler = _mock_factory(lambda request: httpx.Response(200))
    async with RCSBClient(client_factory=handler) as client:
        yield client


async def _run_entry(handler, sleep_recorder, *, pdb_id="6OAV", **retry_overrides):
    """Drive get_entry through a mock handler with deterministic retry config."""
    async with RCSBClient(
        client_factory=_mock_factory(handler),
        config=_det_config(**retry_overrides),
        sleep=sleep_recorder,
    ) as rcsb:
        return await rcsb.get_entry(pdb_id)


async def test_permanent_error_returns_none(sleep_recorder):
    """A 404 is permanent: get_entry swallows it to None, no retries."""
    handler = _fail_then_succeed(99, 404)
    assert await _run_entry(handler, sleep_recorder, pdb_id="ZZZZ") is None
    assert handler.calls["n"] == 1
    assert sleep_recorder.calls == []


def test_to_legacy(rcsb):
    assert rcsb._to_legacy("6OAV") == "6oav"
    assert rcsb._to_legacy("pdb_00006oav") == "6oav"
    assert rcsb._to_legacy("PDB_00006OAV") == "6oav"
    assert rcsb._to_legacy("pdb_12346oav") is None
    assert rcsb._to_legacy("xyz") is None


def test_entry_accessors_xray():
    """All accessors on a complete X-ray payload (offline)."""
    e = RCSBEntry.model_validate(_ENTRY_6OAV)
    assert e.pdb_id == "6OAV"
    assert e.is_xray
    assert e.resolution == 1.939
    assert e.r_factors == {"r_work": 0.2001, "r_free": 0.236}
    assert e.clashscore == 4.25
    assert e.wilson_b == 29.663
    assert not e.has_covalent_bonds
    assert e.has_ligands
    assert e.entity_ids == {"polymer": ["1"], "nonpolymer": ["2"]}
    assert e.mutations_count is None
    assert e.nonpolymer_names is None
    assert e.ligand_smiles is None
    assert e.has_mutations is False


def test_entry_accessors_non_xray():
    """X-ray accessors return None on a non-X-ray payload."""
    e = RCSBEntry.model_validate(_ENTRY_10UJ)
    assert not e.is_xray
    assert e.resolution == 3.9
    assert e.r_factors is e.wilson_b is None
    assert e.clashscore == 2.62
    assert not e.has_ligands


def test_parser_defaults():
    """Model accessors return None/empty on missing data."""
    empty = RCSBEntry.model_validate({"rcsb_entry_info": {}})
    assert (
        empty.resolution
        is empty.r_factors
        is empty.clashscore
        is empty.wilson_b
        is None
    )

    sparse = RCSBEntry.model_validate(
        {
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
            "pdbx_vrpt_summary_geometry": [],
            "pdbx_vrpt_summary_diffraction": [],
            "refine": [],
        }
    )
    assert sparse.is_xray
    assert (
        sparse.resolution
        is sparse.r_factors
        is sparse.clashscore
        is sparse.wilson_b
        is None
    )


@pytest.mark.parametrize(
    "counts, expected",
    [(None, False), ({}, False), ({"1": 0}, False), ({"1": 3}, True)],
)
def test_has_mutations_logic(counts, expected):
    """has_mutations across None / empty / zero / positive counts (offline)."""
    e = RCSBEntry.model_validate({**_ENTRY_6OAV, "mutations_count": counts})
    assert e.has_mutations is expected


def test_extract_smiles():
    """Test SMILES extraction from chemical component records."""
    data = {
        "rcsb_chem_comp_descriptor": {
            "SMILES": "CCO",
            "SMILES_stereo": "CC[OH]",
        }
    }
    assert RCSBClient.extract_smiles(data) == {
        "smiles": "CCO",
        "stereo_smiles": "CC[OH]",
    }

    data = {
        "rcsb_chem_comp_descriptor": {},
        "pdbx_chem_comp_descriptor": [
            {"type": "InChI", "descriptor": "InChI=1S/..."},
            {"type": "SMILES_CANONICAL", "descriptor": "CCO"},
        ],
    }
    assert RCSBClient.extract_smiles(data) == {
        "smiles": "CCO",
        "stereo_smiles": "CCO",
    }

    assert RCSBClient.extract_smiles({}) == {"smiles": "", "stereo_smiles": ""}


async def test_get_entry(rcsb):
    """Entry fetch works with both legacy and extended IDs."""
    legacy = await rcsb.get_entry("6OAV")
    extended = await rcsb.get_entry("pdb_00006oav")
    assert legacy is not None and extended is not None
    assert legacy.is_xray
    assert legacy.pdb_id.lower() == extended.pdb_id.lower()


async def test_entity_lookup(entry_6oav, enriched_entry_6oav, rcsb):
    """Entity IDs from the entry record & non-polymer name resolution."""
    ids = entry_6oav.entity_ids
    assert ids["polymer"] == ["1"]
    assert ids["nonpolymer"][0] == "2"
    assert entry_6oav.has_ligands
    names = await rcsb.nonpolymer_names(entry_6oav)
    assert names == enriched_entry_6oav.nonpolymer_names
    assert "M3A" in names.values()
    assert enriched_entry_6oav.mutations_count["1"] == 3
    assert enriched_entry_6oav.has_mutations


async def test_get_ligand_smiles(rcsb):
    """SMILES & stereo SMILES for the M3A ligand."""
    result = await rcsb.get_ligand_smiles("M3A")
    expected = "c1ccc(cc1)NC(=O)n2c(nc(n2)Nc3ccc(cc3)C#N)N"
    assert result["smiles"] == expected
    assert result["stereo_smiles"] == expected


async def test_get_structure(rcsb):
    """Structure download: legacy ID, extended ID, and unknown ID."""
    result = await rcsb.get_structure("6OAV")
    assert result is not None
    text, fmt = result
    assert fmt == "pdb" and text.startswith("HEADER")

    result = await rcsb.get_structure("pdb_00006oav")
    assert result is not None
    text, fmt = result
    assert fmt == "pdb" and text.startswith("HEADER")
    assert await rcsb.get_structure("ZZZZ") is None
    assert await rcsb.get_ligand_smiles("ZZZZ") == {"smiles": "", "stereo_smiles": ""}


async def test_get_structure_cif_fallback(rcsb):
    """Test that CIF fallback works when PDB download fails."""
    result = await rcsb.get_structure("10AD")
    assert result is not None
    text, fmt = result
    assert fmt == "cif"
    assert text.startswith("data_")
    entry = await rcsb.get_enriched_entry("10AD")
    assert all(len(code) in (3, 5) for code in entry.ligand_smiles)
    names = await rcsb.nonpolymer_names(entry)
    assert "CA" in names.values()
    assert "MG" in names.values()
    assert "A1E02" in names.values()
    assert "CA" not in entry.ligand_smiles


async def test_rcsbclient_caches(tmp_path):
    counter = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        counter["n"] += 1
        return httpx.Response(200, json=_ENTRY_6OAV)

    factory = AlwaysCachePolicy(
        database_path=str(tmp_path / "c.db")
    ).build_client_factory(next_transport=httpx.MockTransport(handler))

    async with RCSBClient(client_factory=factory) as rcsb:
        a = await rcsb.get_entry("6OAV")
        b = await rcsb.get_entry("6OAV")
    assert os.path.exists(tmp_path / "c.db")
    assert a is not None and b is not None
    assert a.resolution == b.resolution == 1.939
    assert counter["n"] == 1
    factory = RFCCachePolicy(database_path=str(tmp_path / "c.db")).build_client_factory(
        next_transport=httpx.MockTransport(handler)
    )
    async with RCSBClient(client_factory=factory) as rcsb:
        c = await rcsb.get_entry("6OAV")
        d = await rcsb.get_entry("6OAV")
    assert c is not None and d is not None
    assert c.resolution == d.resolution == 1.939
    assert counter["n"] == 3
