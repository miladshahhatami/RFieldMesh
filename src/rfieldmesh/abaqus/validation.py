"""Independent reparsing checks for generated Abaqus files."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass

from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.tokens import canonical_name
from rfieldmesh.abaqus.writer import AssignmentResult
from rfieldmesh.exceptions import UnsafeWriteError


@dataclass(frozen=True, slots=True)
class OutputValidation:
    """Summary of post-write structural and property checks."""

    valid: bool
    checked_elements: int
    checked_materials: int
    output_sha256_matches: bool
    remainder_count: int


def validate_generated_output(
    result: AssignmentResult,
    *,
    expected_youngs_modulus: Mapping[int, float] | None = None,
    expected_density: Mapping[int, float] | None = None,
) -> OutputValidation:
    """Reparse a generated model and verify exact target coverage and properties."""
    payload = result.output_path.read_bytes()
    checksum_matches = hashlib.sha256(payload).hexdigest() == result.output_sha256
    if not checksum_matches:
        raise UnsafeWriteError("Generated output checksum changed before validation.")
    model = parse_abaqus_model(result.output_path)
    part = model.part(result.part_name)
    material_by_element: dict[int, str] = {}
    for section in part.sections:
        labels = part.element_set(section.elset_name).labels
        for label in labels:
            if label in result.generated_material_names:
                if label in material_by_element:
                    raise UnsafeWriteError(
                        f"Generated element {label} has overlapping section assignments."
                    )
                material_by_element[label] = section.material_name

    if set(material_by_element) != set(result.generated_material_names):
        raise UnsafeWriteError("Generated section coverage does not match the target elements.")
    for label, expected_material_name in result.generated_material_names.items():
        actual_material_name = material_by_element[label]
        if canonical_name(actual_material_name) != canonical_name(expected_material_name):
            raise UnsafeWriteError(
                f"Element {label} uses material {actual_material_name!r}, "
                f"expected {expected_material_name!r}."
            )
        material = model.material(actual_material_name)
        if expected_youngs_modulus is not None and not math.isclose(
            material.youngs_modulus or math.nan,
            expected_youngs_modulus[label],
            rel_tol=2.0e-14,
        ):
            raise UnsafeWriteError(f"Young's modulus differs for element {label}.")
        if expected_density is not None and not math.isclose(
            material.density or math.nan,
            expected_density[label],
            rel_tol=2.0e-14,
        ):
            raise UnsafeWriteError(f"Density differs for element {label}.")

    remainder_count = 0
    if result.remainder_set_name is not None:
        remainder_count = len(part.element_set(result.remainder_set_name).labels)
    return OutputValidation(
        valid=True,
        checked_elements=len(material_by_element),
        checked_materials=len(result.generated_material_names),
        output_sha256_matches=True,
        remainder_count=remainder_count,
    )
