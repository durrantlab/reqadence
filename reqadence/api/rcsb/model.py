# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 University of Pittsburgh — Of the Commonwealth System of Higher Education
# Source: https://github.com/durrantlab/reqadence


"""Pydantic models for RCSB entry payloads."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class _EntryInfo(BaseModel):
    """Container for entry info."""

    resolution_combined: list[float] | None = None
    """Combined resolution in Å, or None if not reported."""

    inter_mol_covalent_bond_count: int = 0
    """Number of inter-molecular covalent bonds in the entry."""

    nonpolymer_entity_count: int = 0
    """Number of non-polymer entities (ligands, cofactors, etc.) in the entry."""


class _Refine(BaseModel):
    """Container for refinement info."""

    r_work: float | None = Field(
        default=None,
        alias="ls_R_factor_R_work",
        description="R-work factor from refinement (X-ray only).",
    )
    r_free: float | None = Field(
        default=None,
        alias="ls_R_factor_R_free",
        description="R-free factor from refinement (X-ray only).",
    )


class _Exptl(BaseModel):
    """Container for experimental method info."""

    method: str = ""
    """Experimental method used to determine the structure (e.g. ``X-RAY DIFFRACTION``)."""


class _Geometry(BaseModel):
    """Container for geometry validation info."""

    clashscore: float | None = None
    """MolProbity all-atom clashscore from validation report, or None if unavailable."""


class _Diffraction(BaseModel):
    """Container for diffraction data."""

    wilson_b: float | None = Field(
        default=None,
        alias="Wilson_B_estimate",
        description="Wilson B-factor estimate in Å² (X-ray only).",
    )


class _ContainerIdentifiers(BaseModel):
    """Container for polymer and non-polymer entity IDs."""

    polymer_entity_ids: list[str] = Field(
        default_factory=list,
        description="Identifiers for polymer entities in the entry.",
    )
    non_polymer_entity_ids: list[str] = Field(
        default_factory=list,
        description="Identifiers for non-polymer entities (ligands, cofactors, etc.).",
    )


class RCSBEntry(BaseModel):
    """A parsed RCSB entry record."""

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    pdb_id: str = Field(
        default="", alias="rcsb_id", description="The PDB ID of the entry."
    )
    rcsb_entry_info: _EntryInfo = Field(
        default_factory=_EntryInfo, description="Container for entry info."
    )
    refine: list[_Refine] | None = None
    """Container for refinement info (X-ray only)."""

    exptl: list[_Exptl] = Field(
        default_factory=list, description="Container for experimental method info."
    )

    pdbx_geometry_summary: list[_Geometry] | None = Field(
        default=None,
        alias="pdbx_vrpt_summary_geometry",
        description="Container for geometry validation info.",
    )
    pdbx_diffraction_summary: list[_Diffraction] | None = Field(
        default=None,
        alias="pdbx_vrpt_summary_diffraction",
        description="Container for diffraction data.",
    )
    rcsb_entry_container_identifiers: _ContainerIdentifiers = Field(
        default_factory=_ContainerIdentifiers,
        description="Container for polymer and non-polymer entity IDs.",
    )

    mutations_count: dict[str, int] | None = None
    """Count of reported mutations per polymer entity, or None if not reported."""
    nonpolymer_names: dict[str, str] | None = None
    """Mapping of non-polymer entity IDs to their names, or None if not reported."""
    ligand_smiles: dict[str, dict[str, str]] | None = None
    """SMILES strings per non-polymer entity ID, keyed by SMILES type."""

    @property
    def is_xray(self) -> bool:
        """True if the experimental method is X-ray diffraction."""
        return any("X-RAY" in e.method.upper() for e in self.exptl)

    @property
    def resolution(self) -> float | None:
        """Combined resolution in Å, or None if not reported."""
        res = self.rcsb_entry_info.resolution_combined
        return float(res[0]) if res else None

    @property
    def r_factors(self) -> dict[str, float] | None:
        """R-work and R-free from refinement (X-ray only), else None."""
        if not self.is_xray or not self.refine:
            return None
        r_work = self.refine[0].r_work
        r_free = self.refine[0].r_free
        if r_work is None or r_free is None:
            return None
        return {"r_work": r_work, "r_free": r_free}

    @property
    def clashscore(self) -> float | None:
        """MolProbity clashscore, or None if no validation report."""
        if not self.pdbx_geometry_summary:
            return None
        return self.pdbx_geometry_summary[0].clashscore

    @property
    def wilson_b(self) -> float | None:
        """Wilson B-factor estimate in Å² (X-ray only), else None."""
        if not self.is_xray or not self.pdbx_diffraction_summary:
            return None
        return self.pdbx_diffraction_summary[0].wilson_b

    @property
    def has_covalent_bonds(self) -> bool:
        """True if the entry reports any inter-molecular covalent bonds."""
        return self.rcsb_entry_info.inter_mol_covalent_bond_count > 0

    @property
    def has_ligands(self) -> bool:
        """True if the entry has any non-polymer entities."""
        return self.rcsb_entry_info.nonpolymer_entity_count > 0

    @property
    def has_mutations(self) -> bool:
        """True if any polymer entity has reported mutations."""
        if self.mutations_count is None:
            return False
        return any(count > 0 for count in self.mutations_count.values())

    @property
    def entity_ids(self) -> dict[str, list[str]]:
        """Polymer and non-polymer entity IDs from the entry record."""
        ids = self.rcsb_entry_container_identifiers
        return {
            "polymer": ids.polymer_entity_ids,
            "nonpolymer": ids.non_polymer_entity_ids,
        }
