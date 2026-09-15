# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence

"""RCSBClient Protein Data Bank API client and entry model."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from pydantic import BaseModel, ValidationError

from reqadence.api.base import BaseAPI, ClientConfig
from reqadence.api.cache import AlwaysCachePolicy
from reqadence.api.errors import PermanentAPIError
from reqadence.api.rcsb.model import (
    ChemComp,
    NonpolymerEntity,
    PolymerEntity,
    RCSBEntry,
)

RCSB_BASE_URL = "https://data.rcsb.org/rest/v1"
"""Base URL for the RCSBClient REST API endpoints."""

RCSB_FILES_URL = "https://files.rcsb.org/download"
"""Base URL for the RCSBClient file download service."""

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class RCSBClient(BaseAPI):
    """Client for the RCSBClient REST API and file download service.
    Supports both legacy 4-character PDB IDs and newer 12-character IDs.
    """

    def __init__(
        self,
        base_url: str = RCSB_BASE_URL,
        client_factory: Callable[..., httpx.AsyncClient] | None = None,
        *,
        config: ClientConfig | None = None,
        rate_limiter: AsyncLimiter | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Initialize the RCSBClient with caching enabled by default.

        Args:
            base_url: Base URL for the RCSBClient API endpoints.
            client_factory: The RCSBClient client factory. Defaults is `AlwaysCachePolicy`
        """
        if client_factory is None:
            client_factory = AlwaysCachePolicy().build_client_factory()
        super().__init__(
            base_url=base_url,
            client_factory=client_factory,
            config=config,
            rate_limiter=rate_limiter,
            sleep=sleep,
        )

    @staticmethod
    def _to_legacy(pdb_id: str) -> str | None:
        """Convert a PDB ID to its 4-character legacy form, if one exists.
        NOTE: This is a temporary workaround. The RCSBClient data API does not
        currently accept extended IDs. This bridge can be removed once RCSBClient
        extends data API support.
        """
        pdb_id = pdb_id.lower()
        if len(pdb_id) == 4:
            return pdb_id
        if len(pdb_id) == 12 and pdb_id.startswith("pdb_0000"):
            return pdb_id[-4:]
        return None

    async def _get_model(
        self, url: str, model: type[_ModelT], context: str
    ) -> _ModelT | None:
        """GET a JSON object and validate it into the given pydantic model.

        Args:
            url: Endpoint path to fetch.
            model: The pydantic model class to validate the payload into.
            context: Human-readable subject for log messages (e.g. the PDB ID).

        Returns:
            The validated model instance, or None if the request failed, the
            payload was not a JSON object, or validation failed.
        """
        try:
            data = await self._get_json(url)
        except PermanentAPIError:
            return None
        if not isinstance(data, dict):
            return None
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            logger.error(
                "Failed to validate {model} for {context}: {exc}",
                model=model.__name__,
                context=context,
                exc=exc,
            )
            return None

    async def get_entry(self, pdb_id: str) -> RCSBEntry | None:
        """Fetch an entry record. Accepts legacy or extended PDB IDs.

        Args:
            pdb_id: 4-character legacy PDB ID or 12-character extended ID.

        Returns:
            An `RCSBEntry` object if found, or None if not found.
        """
        pdb_id = self._to_legacy(pdb_id) or pdb_id
        return await self._get_model(f"core/entry/{pdb_id}", RCSBEntry, context=pdb_id)

    async def _get_polymer_entity(
        self, pdb_id: str, entity_id: str
    ) -> PolymerEntity | None:
        """Fetch a polymer entity record for the given PDB ID and entity ID.

        Args:
            pdb_id: 4-character legacy PDB ID or 12-character extended ID.
            entity_id: The polymer entity ID.

        Returns:
            A `PolymerEntity` if found, or None if not found.
        """
        pdb_id = self._to_legacy(pdb_id) or pdb_id
        return await self._get_model(
            f"core/polymer_entity/{pdb_id}/{entity_id}",
            PolymerEntity,
            context=f"{pdb_id}/{entity_id}",
        )

    async def _get_nonpolymer_entity(
        self, pdb_id: str, entity_id: str
    ) -> NonpolymerEntity | None:
        """Fetch a non-polymer entity record for the given PDB ID and entity ID.

        Args:
            pdb_id: 4-character legacy PDB ID or 12-character extended ID.
            entity_id: The non-polymer entity ID.

        Returns:
            A `NonpolymerEntity` if found, or None if not found.
        """
        pdb_id = self._to_legacy(pdb_id) or pdb_id
        return await self._get_model(
            f"core/nonpolymer_entity/{pdb_id}/{entity_id}",
            NonpolymerEntity,
            context=f"{pdb_id}/{entity_id}",
        )

    async def _get_chemcomp(self, comp_id: str) -> ChemComp | None:
        """Fetch a chemical component record (e.g. for SMILES lookup).

        Args:
            comp_id: The chemical component ID.

        Returns:
            A `ChemComp` if found, or None if not found.
        """
        return await self._get_model(
            f"core/chemcomp/{comp_id}", ChemComp, context=comp_id
        )

    async def get_structure(self, pdb_id: str) -> tuple[str, str] | None:
        """Download a structure as PDB, falling back to mmCIF if PDB is not available.

        Args:
            pdb_id: 4-character legacy PDB ID or 12-character extended ID.

        Returns:
            A (text, format) tuple where format is "pdb" or "cif", or None
            if neither could be retrieved.
        """
        pdb_id = pdb_id.lower()
        legacy_id = self._to_legacy(pdb_id)
        if legacy_id is not None:
            try:
                pdb_resp = await self._get(f"{RCSB_FILES_URL}/{legacy_id}.pdb")
                return pdb_resp.text, "pdb"
            except PermanentAPIError:
                logger.warning(
                    "PDB file not found for {pdb_id}. Trying mmCIF.", pdb_id=pdb_id
                )
        try:
            cif_resp = await self._get(f"{RCSB_FILES_URL}/{pdb_id}.cif")
            return cif_resp.text, "cif"
        except PermanentAPIError:
            logger.error("Could not download structure for {pdb_id}.", pdb_id=pdb_id)
            return None

    async def get_ligand_smiles(self, comp_id: str) -> dict[str, str]:
        """SMILES & stereo SMILES for a chemical component (3- or 5-char code).

        Args:
            comp_id: The chemical component ID.

        Returns:
            A dictionary containing the SMILES and stereo SMILES,
                or an empty dictionary if not found.
        """
        data = await self._get_chemcomp(comp_id)
        if data is None:
            return {"smiles": "", "stereo_smiles": ""}
        return self.extract_smiles(data)

    @staticmethod
    def extract_smiles(chemcomp: ChemComp) -> dict[str, str]:
        """Extract canonical and stereo SMILES from a chem component record.
        Falls back to pdbx_chem_comp_descriptor: SMILES_CANONICAL when the
        rcsb_chem_comp_descriptor block is missing the smiles field.

        Args:
            chemcomp: The parsed chemical component record from the API.
        Returns:
            A dictionary containing the SMILES and stereo SMILES, or an empty
                dictionary if not found
        """
        descriptor = chemcomp.rcsb_chem_comp_descriptor
        if descriptor is not None and descriptor.smiles is not None:
            return {
                "smiles": descriptor.smiles,
                "stereo_smiles": descriptor.smiles_stereo or descriptor.smiles,
            }
        for row in chemcomp.pdbx_chem_comp_descriptor:
            if row.type == "SMILES_CANONICAL":
                return {"smiles": row.descriptor, "stereo_smiles": row.descriptor}

        logger.warning("No SMILES found in chem component record.")
        return {"smiles": "", "stereo_smiles": ""}

    async def mutations_count(self, entry: RCSBEntry) -> dict[str, int]:
        """Map the polymer entities to their mutation counts.

        Args:
            entry: An RCSBEntry object.

        Returns:
            A dictionary mapping polymer entity IDs to their mutation counts.
        """
        counts: dict[str, int] = {}
        for entity_id in entry.entity_ids["polymer"]:
            data = await self._get_polymer_entity(entry.pdb_id, entity_id)
            if data is None:
                logger.warning(
                    "Failed to fetch polymer entity {entity_id} for {pdb_id}.",
                    entity_id=entity_id,
                    pdb_id=entry.pdb_id,
                )
                continue
            counts[entity_id] = data.entity_poly.rcsb_mutation_count
        return counts

    async def nonpolymer_names(self, entry: RCSBEntry) -> dict[str, str]:
        """Map the non-polymer entities to their names.

        Args:
            entry: An RCSBEntry object.

        Returns:
            A dictionary mapping non-polymer entity IDs to their names.
        """
        if not entry.has_ligands:
            return {}
        names: dict[str, str] = {}
        for entity_id in entry.entity_ids["nonpolymer"]:
            data = await self._get_nonpolymer_entity(entry.pdb_id, entity_id)
            if data is None:
                logger.warning(
                    "Failed to fetch nonpolymer entity {entity_id} for {pdb_id}.",
                    entity_id=entity_id,
                    pdb_id=entry.pdb_id,
                )
                continue
            comp_id = data.pdbx_entity_nonpoly.comp_id
            if comp_id:
                names[entity_id] = comp_id
        return names

    async def enrich(self, entry: RCSBEntry) -> RCSBEntry:
        """Inject the  mutation counts, ligand names, and ligand SMILES into the entry.

        Args:
            entry: A previously fetched entry to populate in place.

        Returns:
            The same entry, with its enrichment fields filled in.
        """
        entry.mutations_count = await self.mutations_count(entry)
        names = await self.nonpolymer_names(entry)
        entry.nonpolymer_names = names
        smiles_codes = list(
            dict.fromkeys(c for c in names.values() if len(c) in (3, 5))
        )
        entry.ligand_smiles = {
            comp_id: await self.get_ligand_smiles(comp_id) for comp_id in smiles_codes
        }
        return entry

    async def get_enriched_entry(self, pdb_id: str) -> RCSBEntry | None:
        """Fetch an entry and immediately enrich it. None if not found.

        Args:
            pdb_id: 4-character legacy PDB ID or 12-character extended ID.

        Returns:
            An enriched `RCSBEntry` object if found, or None if not found.
        """
        entry = await self.get_entry(pdb_id)
        if entry is None:
            return None
        return await self.enrich(entry)
