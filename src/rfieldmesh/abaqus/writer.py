"""Patch-based writer for portable per-element material assignment."""

from __future__ import annotations

import hashlib
import math
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from rfieldmesh.abaqus.model import AbaqusModel, MaterialDefinition
from rfieldmesh.abaqus.regions import ResolvedRegion
from rfieldmesh.abaqus.tokens import KeywordToken, canonical_name
from rfieldmesh.exceptions import UnsafeWriteError, UnsupportedModelError


@dataclass(frozen=True, slots=True)
class Patch:
    """One nonoverlapping source-text replacement or insertion."""

    start: int
    end: int
    replacement: str
    reason: str


@dataclass(frozen=True, slots=True)
class AssignmentResult:
    """Provenance returned after a successful atomic write."""

    output_path: Path
    output_sha256: str
    output_size_bytes: int
    source_sha256: str
    part_name: str
    instance_name: str | None
    selected_set_name: str
    target_count: int
    excluded_count: int
    generated_set_names: dict[int, str]
    generated_material_names: dict[int, str]
    remainder_set_name: str | None
    source_material_name: str


def _format_number(value: float) -> str:
    return f"{value:.15g}"


def _validate_values(
    name: str,
    values: Mapping[int, float] | None,
    expected_labels: tuple[int, ...],
) -> dict[int, float] | None:
    if values is None:
        return None
    normalized = {int(label): float(value) for label, value in values.items()}
    if set(normalized) != set(expected_labels):
        missing = len(set(expected_labels) - set(normalized))
        extra = len(set(normalized) - set(expected_labels))
        raise UnsafeWriteError(
            f"{name} values do not match the eligible region: {missing} missing, {extra} extra."
        )
    if any(not math.isfinite(value) or value <= 0.0 for value in normalized.values()):
        raise UnsafeWriteError(f"Every {name} value must be positive and finite.")
    return normalized


def _token_content_end(model: AbaqusModel, token: KeywordToken) -> int:
    offset = token.data_start
    for line in model.source.text[token.data_start : token.data_end].splitlines(keepends=True):
        if line.lstrip().startswith("**"):
            return offset
        offset += len(line)
    return token.data_end


def _material_property_rows(model: AbaqusModel, token_index: int) -> list[str]:
    token = model.tokens[token_index]
    return [
        line.strip()
        for line in model.source.text[token.data_start : token.data_end].splitlines()
        if line.strip() and not line.lstrip().startswith("**")
    ]


def _validate_cloneable_material(
    model: AbaqusModel,
    material: MaterialDefinition,
    *,
    replace_youngs_modulus: bool,
    replace_density: bool,
) -> None:
    if replace_density:
        if material.density_token_index is None:
            raise UnsupportedModelError(
                f"Material {material.name!r} has no scalar *Density definition."
            )
        density_token = model.tokens[material.density_token_index]
        disallowed = set(density_token.parameters) - {"density"}
        if disallowed or len(_material_property_rows(model, density_token.index)) != 1:
            raise UnsupportedModelError(
                "Temperature/field-dependent or multirow *Density data are not supported."
            )
    if replace_youngs_modulus:
        if material.elastic_token_index is None:
            raise UnsupportedModelError(
                f"Material {material.name!r} has no isotropic *Elastic definition."
            )
        elastic_token = model.tokens[material.elastic_token_index]
        elastic_type = elastic_token.parameter("type")
        disallowed = set(elastic_token.parameters) - {"type"}
        if (
            disallowed
            or (elastic_type is not None and elastic_type.casefold() != "isotropic")
            or len(_material_property_rows(model, elastic_token.index)) != 1
        ):
            raise UnsupportedModelError(
                "Only one-row isotropic *Elastic data without dependencies are supported."
            )


def _replace_material_name(line: str, new_name: str) -> str:
    pattern = re.compile(r"(?i)(\bname\s*=\s*)(?:\"[^\"]*\"|[^,\r\n]+)")
    replacement, count = pattern.subn(lambda match: match.group(1) + new_name, line, count=1)
    if count != 1:
        raise UnsafeWriteError("Could not replace the cloned *Material name safely.")
    return replacement


def _replace_first_csv_value(line: str, value: float) -> str:
    line_ending = ""
    body = line
    if body.endswith("\r\n"):
        body, line_ending = body[:-2], "\r\n"
    elif body.endswith(("\n", "\r")):
        body, line_ending = body[:-1], body[-1]
    match = re.match(r"^(\s*)[^,\r\n]*(.*)$", body)
    if match is None:
        raise UnsafeWriteError("Could not replace a material-property value safely.")
    return f"{match.group(1)}{_format_number(value)}{match.group(2)}{line_ending}"


def _clone_material(
    model: AbaqusModel,
    material: MaterialDefinition,
    *,
    new_name: str,
    youngs_modulus: float | None,
    density: float | None,
) -> str:
    block = model.source.text[material.start : material.end]
    lines = block.splitlines(keepends=True)
    mode: str | None = None
    replaced_name = False
    replaced_elastic = youngs_modulus is None
    replaced_density = density is None
    output: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("*") and not stripped.startswith("**"):
            keyword = stripped[1:].split(",", 1)[0].strip().casefold()
            mode = keyword
            if keyword == "material" and not replaced_name:
                line = _replace_material_name(line, new_name)
                replaced_name = True
        elif stripped and not stripped.startswith("**"):
            if mode == "elastic" and not replaced_elastic and youngs_modulus is not None:
                line = _replace_first_csv_value(line, youngs_modulus)
                replaced_elastic = True
            elif mode == "density" and not replaced_density and density is not None:
                line = _replace_first_csv_value(line, density)
                replaced_density = True
        output.append(line)
    if not (replaced_name and replaced_elastic and replaced_density):
        raise UnsafeWriteError("The source material could not be cloned completely.")
    return "".join(output)


def _label_lines(labels: tuple[int, ...], newline: str) -> str:
    rows = []
    for start in range(0, len(labels), 16):
        rows.append(", ".join(str(label) for label in labels[start : start + 16]))
    return newline.join(rows) + newline


def _unique_name(base: str, occupied: set[str]) -> str:
    candidate = base[:80]
    index = 1
    while canonical_name(candidate) in occupied:
        suffix = f"_{index}"
        candidate = f"{base[: 80 - len(suffix)]}{suffix}"
        index += 1
    occupied.add(canonical_name(candidate))
    return candidate


def _apply_patches(text: str, patches: list[Patch]) -> str:
    ordered = sorted(patches, key=lambda patch: (patch.start, patch.end))
    previous_end = 0
    for patch in ordered:
        if patch.start < previous_end or patch.start < 0 or patch.end < patch.start:
            raise UnsafeWriteError("The generated patch plan contains overlapping spans.")
        if patch.end > len(text):
            raise UnsafeWriteError("A generated patch lies outside the source file.")
        previous_end = patch.end
    result = text
    for patch in reversed(ordered):
        result = result[: patch.start] + patch.replacement + result[patch.end :]
    return result


def _publish_temporary(
    temporary_name: str,
    destination: Path,
    *,
    overwrite: bool,
) -> None:
    """Publish atomically without silently overwriting when overwrite is false."""
    if overwrite:
        os.replace(temporary_name, destination)
        return
    try:
        os.link(temporary_name, destination)
    except FileExistsError as exc:
        raise UnsafeWriteError(f"Output already exists: {destination}") from exc
    os.unlink(temporary_name)


def write_elementwise_materials(
    model: AbaqusModel,
    region: ResolvedRegion,
    output_path: str | Path,
    *,
    youngs_modulus: Mapping[int, float] | None = None,
    density: Mapping[int, float] | None = None,
    name_prefix: str = "RFM",
    overwrite: bool = False,
) -> AssignmentResult:
    """Clone the complete source material per eligible target element and write atomically."""
    if youngs_modulus is None and density is None:
        raise UnsafeWriteError("At least one material property must be randomized.")
    youngs_values = _validate_values("Young's-modulus", youngs_modulus, region.eligible_labels)
    density_values = _validate_values("density", density, region.eligible_labels)
    source_material = model.material(region.coverage.source_material_name)
    _validate_cloneable_material(
        model,
        source_material,
        replace_youngs_modulus=youngs_values is not None,
        replace_density=density_values is not None,
    )

    destination = Path(output_path).expanduser().resolve()
    if destination == model.source.path:
        raise UnsafeWriteError("The generated model must not overwrite its source file.")
    if destination.exists() and not overwrite:
        raise UnsafeWriteError(f"Output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    model.source.verify_unchanged()

    newline = model.source.newline
    normalized_prefix = re.sub(r"[^A-Za-z0-9_]", "_", name_prefix).strip("_") or "RFM"
    occupied_sets = {canonical_name(item.name) for item in region.part.element_sets.values()}
    occupied_materials = set(model.materials)
    generated_sets: dict[int, str] = {}
    generated_materials: dict[int, str] = {}

    section_text: list[str] = []
    remainder_name: str | None = None
    if region.coverage.remainder_labels:
        remainder_name = _unique_name(
            f"{normalized_prefix}_REMAINDER",
            occupied_sets,
        )
        section_text.extend(
            [
                f"*Elset, elset={remainder_name}{newline}",
                _label_lines(region.coverage.remainder_labels, newline),
                (
                    f"*Solid Section, elset={remainder_name}, "
                    f"material={source_material.name}{newline}"
                ),
                f",{newline}",
            ]
        )

    material_text: list[str] = []
    for label in region.eligible_labels:
        set_name = _unique_name(f"{normalized_prefix}_E_{label}", occupied_sets)
        material_name = _unique_name(f"{normalized_prefix}_M_{label}", occupied_materials)
        generated_sets[label] = set_name
        generated_materials[label] = material_name
        section_text.extend(
            [
                f"*Elset, elset={set_name}{newline}",
                f"{label}{newline}",
                (f"*Solid Section, elset={set_name}, material={material_name}{newline}"),
                f",{newline}",
            ]
        )
        material_text.append(
            _clone_material(
                model,
                source_material,
                new_name=material_name,
                youngs_modulus=(None if youngs_values is None else youngs_values[label]),
                density=None if density_values is None else density_values[label],
            )
        )

    section_token = model.tokens[region.coverage.section.token_index]
    insertion_position = max(material.end for material in model.materials.values())
    patches = [
        Patch(
            start=section_token.start,
            end=_token_content_end(model, section_token),
            replacement="".join(section_text),
            reason="replace original section coverage",
        ),
        Patch(
            start=insertion_position,
            end=insertion_position,
            replacement="".join(material_text),
            reason="insert cloned element materials",
        ),
    ]
    output_text = _apply_patches(model.source.text, patches)
    payload = model.source.encode(output_text)

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        _publish_temporary(temporary_name, destination, overwrite=overwrite)
    except (OSError, UnsafeWriteError) as exc:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        if isinstance(exc, UnsafeWriteError):
            raise
        raise UnsafeWriteError(f"Could not write generated model: {destination}") from exc

    return AssignmentResult(
        output_path=destination,
        output_sha256=hashlib.sha256(payload).hexdigest(),
        output_size_bytes=len(payload),
        source_sha256=model.source.sha256,
        part_name=region.part.name,
        instance_name=None if region.instance is None else region.instance.name,
        selected_set_name=region.set_name,
        target_count=len(region.eligible_labels),
        excluded_count=sum(len(labels) for labels in region.excluded_by_type.values()),
        generated_set_names=generated_sets,
        generated_material_names=generated_materials,
        remainder_set_name=remainder_name,
        source_material_name=source_material.name,
    )
