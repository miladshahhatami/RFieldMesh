"""Unsaved random-field preview application service."""

from __future__ import annotations

from dataclasses import dataclass

from rfieldmesh.abaqus.model import AbaqusModel
from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import ResolvedRegion, resolve_region
from rfieldmesh.application.generate import FieldGeneration, generate_property_fields
from rfieldmesh.config.models import GenerationConfig


@dataclass(frozen=True, slots=True)
class PreviewResult:
    """Generated fields and resolved geometry without an Abaqus write."""

    config: GenerationConfig
    model: AbaqusModel
    region: ResolvedRegion
    fields: tuple[FieldGeneration, ...]

    @property
    def eligible_count(self) -> int:
        """Return the number of visualized and eventually randomized elements."""
        return len(self.region.eligible_labels)

    @property
    def excluded_count(self) -> int:
        """Return the number of selected elements excluded by eligibility rules."""
        return sum(len(labels) for labels in self.region.excluded_by_type.values())


def preview_model(config: GenerationConfig) -> PreviewResult:
    """Resolve a model region and generate configured fields without writing files."""
    model = parse_abaqus_model(config.source_path)
    region = resolve_region(
        model,
        part_name=config.part_name,
        set_name=config.set_name,
        instance_name=config.instance_name,
    )
    fields = generate_property_fields(region, config)
    return PreviewResult(
        config=config,
        model=model,
        region=region,
        fields=fields,
    )
