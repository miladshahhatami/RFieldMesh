"""Lossless Abaqus input-file inspection and safe modification."""

from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import ResolvedRegion, resolve_region
from rfieldmesh.abaqus.source import AbaqusSource
from rfieldmesh.abaqus.validation import OutputValidation, validate_generated_output
from rfieldmesh.abaqus.writer import AssignmentResult, write_elementwise_materials

__all__ = [
    "AbaqusSource",
    "AssignmentResult",
    "OutputValidation",
    "ResolvedRegion",
    "parse_abaqus_model",
    "resolve_region",
    "validate_generated_output",
    "write_elementwise_materials",
]
