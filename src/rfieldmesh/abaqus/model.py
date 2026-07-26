"""Semantic domain objects projected from Abaqus keyword files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from rfieldmesh.abaqus.source import AbaqusSource
from rfieldmesh.abaqus.tokens import KeywordToken, canonical_name
from rfieldmesh.exceptions import AbaqusParseError

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class ElementRecord:
    """One finite element with its source type and connectivity."""

    label: int
    element_type: str
    connectivity: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ElementSet:
    """Resolved explicit membership for a part-level element set."""

    name: str
    labels: tuple[int, ...]
    token_index: int


@dataclass(frozen=True, slots=True)
class SolidSection:
    """A part-level solid-section assignment."""

    elset_name: str
    material_name: str
    token_index: int


@dataclass(slots=True)
class Part:
    """Nodes, elements, sets, and sections belonging to one Abaqus part."""

    name: str
    node_coordinates: dict[int, tuple[float, ...]] = field(default_factory=dict)
    elements: dict[int, ElementRecord] = field(default_factory=dict)
    element_sets: dict[str, ElementSet] = field(default_factory=dict)
    sections: list[SolidSection] = field(default_factory=list)

    def element_set(self, name: str) -> ElementSet:
        """Resolve a set by Abaqus' case-insensitive naming convention."""
        try:
            return self.element_sets[canonical_name(name)]
        except KeyError as exc:
            raise AbaqusParseError(
                f"Part {self.name!r} has no element set named {name!r}."
            ) from exc


@dataclass(frozen=True, slots=True)
class InstanceTransform:
    """Rigid part-to-assembly transformation."""

    matrix: FloatArray

    @classmethod
    def identity(cls) -> InstanceTransform:
        return cls(matrix=np.eye(4, dtype=np.float64))

    def apply(self, points: FloatArray) -> FloatArray:
        """Apply the homogeneous transform to an array of 2D or 3D points."""
        coordinates = np.asarray(points, dtype=np.float64)
        original_dimension = coordinates.shape[1]
        padded = np.zeros((coordinates.shape[0], 3), dtype=np.float64)
        padded[:, :original_dimension] = coordinates
        homogeneous = np.column_stack((padded, np.ones(coordinates.shape[0])))
        transformed = homogeneous @ self.matrix.T
        return np.asarray(transformed[:, :original_dimension], dtype=np.float64)


@dataclass(frozen=True, slots=True)
class Instance:
    """One assembly instance of a part."""

    name: str
    part_name: str
    transform: InstanceTransform
    token_index: int


@dataclass(frozen=True, slots=True)
class MaterialDefinition:
    """One source material block and the property cards used by the MVP."""

    name: str
    start: int
    end: int
    material_token_index: int
    density_token_index: int | None
    elastic_token_index: int | None
    density: float | None
    youngs_modulus: float | None
    poissons_ratio: float | None


@dataclass(frozen=True, slots=True)
class AbaqusModel:
    """Complete Phase 4 semantic view of one source input file."""

    source: AbaqusSource
    tokens: tuple[KeywordToken, ...]
    parts: dict[str, Part]
    instances: dict[str, Instance]
    materials: dict[str, MaterialDefinition]
    include_paths: tuple[Path, ...]

    def part(self, name: str) -> Part:
        try:
            return self.parts[canonical_name(name)]
        except KeyError as exc:
            raise AbaqusParseError(f"No part named {name!r} was found.") from exc

    def material(self, name: str) -> MaterialDefinition:
        try:
            return self.materials[canonical_name(name)]
        except KeyError as exc:
            raise AbaqusParseError(f"No material named {name!r} was found.") from exc

    def instance(self, name: str) -> Instance:
        try:
            return self.instances[canonical_name(name)]
        except KeyError as exc:
            raise AbaqusParseError(f"No instance named {name!r} was found.") from exc
