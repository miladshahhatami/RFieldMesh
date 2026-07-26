"""Region, eligibility, geometry, and section-coverage resolution."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from rfieldmesh.abaqus.element_registry import element_descriptor
from rfieldmesh.abaqus.model import AbaqusModel, ElementRecord, Instance, Part, SolidSection
from rfieldmesh.abaqus.tokens import canonical_name
from rfieldmesh.exceptions import AbaqusParseError, GeometryError, UnsupportedModelError

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class SectionCoverage:
    """Unique source section and material covering a resolved target region."""

    section: SolidSection
    source_material_name: str
    section_labels: tuple[int, ...]
    remainder_labels: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ResolvedRegion:
    """Selected and eligible elements with representative coordinates."""

    part: Part
    instance: Instance | None
    set_name: str
    selected_labels: tuple[int, ...]
    eligible_labels: tuple[int, ...]
    excluded_by_type: dict[str, tuple[int, ...]]
    representative_coordinates: FloatArray
    assembly_coordinates: FloatArray
    region_origin: FloatArray
    coverage: SectionCoverage

    @property
    def dimension(self) -> int:
        return int(self.representative_coordinates.shape[1])


def _instance_for_part(
    model: AbaqusModel,
    part: Part,
    instance_name: str | None,
) -> Instance | None:
    if instance_name is not None:
        instance = model.instance(instance_name)
        if canonical_name(instance.part_name) != canonical_name(part.name):
            raise AbaqusParseError(
                f"Instance {instance.name!r} does not instantiate part {part.name!r}."
            )
        return instance
    candidates = [
        instance
        for instance in model.instances.values()
        if canonical_name(instance.part_name) == canonical_name(part.name)
    ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise UnsupportedModelError(
            f"Part {part.name!r} has multiple instances; select one explicitly."
        )
    return None


def _representative_point(part: Part, element: ElementRecord) -> np.ndarray:
    descriptor = element_descriptor(element.element_type)
    if not descriptor.supported:
        raise GeometryError(f"Unsupported element type {element.element_type}.")
    try:
        coordinates = np.asarray(
            [part.node_coordinates[label] for label in element.connectivity],
            dtype=np.float64,
        )
    except KeyError as exc:
        raise AbaqusParseError(
            f"Element {element.label} refers to an undefined node {exc.args[0]}."
        ) from exc
    if coordinates.shape != (descriptor.node_count, descriptor.dimension):
        raise GeometryError(
            f"Element {element.label} coordinate dimension does not match {element.element_type}."
        )
    return np.asarray(np.mean(coordinates, axis=0), dtype=np.float64)


def _region_geometry_origin(
    part: Part,
    labels: list[int],
    instance: Instance | None,
) -> np.ndarray:
    node_labels = {
        node_label for label in labels for node_label in part.elements[label].connectivity
    }
    coordinates = np.asarray(
        [part.node_coordinates[label] for label in sorted(node_labels)],
        dtype=np.float64,
    )
    assembly_coordinates = (
        coordinates if instance is None else instance.transform.apply(coordinates)
    )
    origin = np.asarray(np.min(assembly_coordinates, axis=0), dtype=np.float64)
    coordinate_scale = max(1.0, float(np.max(np.abs(assembly_coordinates))))
    roundoff_tolerance = 64.0 * np.finfo(np.float64).eps * coordinate_scale
    return np.where(np.abs(origin) < roundoff_tolerance, 0.0, origin)


def _resolve_section_coverage(
    part: Part,
    target_labels: tuple[int, ...],
) -> SectionCoverage:
    target = set(target_labels)
    per_element: dict[int, list[SolidSection]] = {label: [] for label in target_labels}
    section_memberships: dict[int, tuple[int, ...]] = {}
    for section in part.sections:
        element_set = part.element_set(section.elset_name)
        section_memberships[section.token_index] = element_set.labels
        for label in target.intersection(element_set.labels):
            per_element[label].append(section)
    missing = [label for label, sections in per_element.items() if not sections]
    ambiguous = [label for label, sections in per_element.items() if len(sections) > 1]
    if missing:
        raise UnsupportedModelError(
            f"{len(missing)} target elements have no *Solid Section assignment."
        )
    if ambiguous:
        raise UnsupportedModelError(
            f"{len(ambiguous)} target elements have overlapping *Solid Section assignments."
        )
    unique_sections = {sections[0].token_index: sections[0] for sections in per_element.values()}
    if len(unique_sections) != 1:
        raise UnsupportedModelError(
            "A random-field region must inherit one original section/material in Phase 4."
        )
    section = next(iter(unique_sections.values()))
    section_labels = section_memberships[section.token_index]
    remainder = tuple(label for label in section_labels if label not in target)
    return SectionCoverage(
        section=section,
        source_material_name=section.material_name,
        section_labels=section_labels,
        remainder_labels=remainder,
    )


def resolve_region(
    model: AbaqusModel,
    *,
    part_name: str,
    set_name: str,
    instance_name: str | None = None,
    region_local_coordinates: bool = True,
) -> ResolvedRegion:
    """Resolve one part-level set into supported target elements and coordinates."""
    if model.include_paths:
        raise UnsupportedModelError(
            "Generation is disabled when *INCLUDE files are present in the Phase 4 checkpoint."
        )
    part = model.part(part_name)
    element_set = part.element_set(set_name)
    instance = _instance_for_part(model, part, instance_name)
    excluded: dict[str, list[int]] = {}
    eligible: list[int] = []
    for label in element_set.labels:
        if label not in part.elements:
            raise AbaqusParseError(
                f"Element set {element_set.name!r} refers to missing element {label}."
            )
        element = part.elements[label]
        descriptor = element_descriptor(element.element_type)
        if descriptor.supported:
            eligible.append(label)
        else:
            excluded.setdefault(element.element_type, []).append(label)
    if not eligible:
        raise UnsupportedModelError("The selected region contains no supported continuum elements.")

    part_points = np.vstack(
        [_representative_point(part, part.elements[label]) for label in eligible]
    )
    assembly_points = part_points if instance is None else instance.transform.apply(part_points)
    origin = (
        _region_geometry_origin(part, eligible, instance)
        if region_local_coordinates
        else np.zeros(assembly_points.shape[1], dtype=np.float64)
    )
    representative = assembly_points - origin
    eligible_labels = tuple(eligible)
    return ResolvedRegion(
        part=part,
        instance=instance,
        set_name=element_set.name,
        selected_labels=element_set.labels,
        eligible_labels=eligible_labels,
        excluded_by_type={
            element_type: tuple(labels) for element_type, labels in sorted(excluded.items())
        },
        representative_coordinates=np.asarray(representative, dtype=np.float64),
        assembly_coordinates=np.asarray(assembly_points, dtype=np.float64),
        region_origin=np.asarray(origin, dtype=np.float64),
        coverage=_resolve_section_coverage(part, eligible_labels),
    )
