"""Patch-based writer for portable per-element material assignment."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from rfieldmesh.abaqus.model import AbaqusModel, MaterialDefinition
from rfieldmesh.abaqus.regions import ResolvedRegion
from rfieldmesh.abaqus.tokens import KeywordToken, canonical_name
from rfieldmesh.config.enums import PropertyKind
from rfieldmesh.config.properties import property_definition
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
    randomized_properties: tuple[PropertyKind, ...]


def _validate_values(
    kind: PropertyKind,
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
            f"{property_definition(kind).display_name} values do not match the eligible "
            f"region: {missing} missing, {extra} extra."
        )
    definition = property_definition(kind)
    invalid = [value for value in normalized.values() if not definition.value_is_valid(value)]
    if invalid:
        raise UnsafeWriteError(
            f"Every {definition.display_name} value must be finite and lie in "
            f"{definition.interval_text}; values were not clipped."
        )
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
    property_kinds: tuple[PropertyKind, ...],
) -> None:
    by_keyword: dict[str, list[PropertyKind]] = {}
    for kind in property_kinds:
        by_keyword.setdefault(property_definition(kind).abaqus_keyword, []).append(kind)
    for keyword, kinds in by_keyword.items():
        token_index = material.property_token_index(kinds[0])
        if token_index is None:
            names = ", ".join(property_definition(kind).display_name for kind in kinds)
            raise UnsupportedModelError(
                f"Material {material.name!r} has no scalar *{keyword.title()} definition "
                f"required for {names}. The constitutive keyword will not be introduced "
                "automatically."
            )
        matching_tokens = [
            token
            for token in model.tokens
            if material.start <= token.start < material.end and token.keyword == keyword
        ]
        if len(matching_tokens) != 1:
            raise UnsupportedModelError(
                f"Material {material.name!r} has {len(matching_tokens)} *{keyword.title()} "
                "definitions; exactly one unambiguous property card is required."
            )
        token = model.tokens[token_index]
        rows = _material_property_rows(model, token.index)
        if keyword == "elastic":
            elastic_type = token.parameter("type")
            disallowed = set(token.parameters) - {"type"}
            if elastic_type is not None and elastic_type.casefold() != "isotropic":
                disallowed.add("type")
        else:
            disallowed = set(token.parameters)
        required_columns = max(property_definition(kind).column_index for kind in kinds) + 1
        row_columns = 0 if not rows else len(rows[0].split(","))
        if disallowed or len(rows) != 1 or row_columns < required_columns:
            raise UnsupportedModelError(
                f"Only one-row scalar *{keyword.title()} data without temperature, field, "
                "or dependency parameters are supported."
            )


def _replace_material_name(line: str, new_name: str) -> str:
    pattern = re.compile(r"(?i)(\bname\s*=\s*)(?:\"[^\"]*\"|[^,\r\n]+)")
    replacement, count = pattern.subn(lambda match: match.group(1) + new_name, line, count=1)
    if count != 1:
        raise UnsafeWriteError("Could not replace the cloned *Material name safely.")
    return replacement


def _replace_csv_value(
    line: str,
    column_index: int,
    value: float,
    kind: PropertyKind,
) -> str:
    line_ending = ""
    body = line
    if body.endswith("\r\n"):
        body, line_ending = body[:-2], "\r\n"
    elif body.endswith(("\n", "\r")):
        body, line_ending = body[:-1], body[-1]
    fields = body.split(",")
    if column_index >= len(fields):
        raise UnsafeWriteError("Could not replace a material-property value safely.")
    original = fields[column_index]
    leading = original[: len(original) - len(original.lstrip())]
    trailing = original[len(original.rstrip()) :]
    fields[column_index] = f"{leading}{property_definition(kind).format_value(value)}{trailing}"
    return ",".join(fields) + line_ending


def _clone_material(
    model: AbaqusModel,
    material: MaterialDefinition,
    *,
    new_name: str,
    property_values: Mapping[PropertyKind, float],
) -> str:
    block = model.source.text[material.start : material.end]
    lines = block.splitlines(keepends=True)
    mode: str | None = None
    replaced_name = False
    replaced: set[PropertyKind] = set()
    by_keyword: dict[str, list[PropertyKind]] = {}
    for kind in property_values:
        by_keyword.setdefault(property_definition(kind).abaqus_keyword, []).append(kind)
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
            for kind in by_keyword.get(mode or "", ()):
                if kind not in replaced:
                    definition = property_definition(kind)
                    line = _replace_csv_value(
                        line,
                        definition.column_index,
                        property_values[kind],
                        kind,
                    )
                    replaced.add(kind)
        output.append(line)
    if not replaced_name or replaced != set(property_values):
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
    property_values: Mapping[PropertyKind, Mapping[int, float]] | None = None,
    youngs_modulus: Mapping[int, float] | None = None,
    density: Mapping[int, float] | None = None,
    poissons_ratio: Mapping[int, float] | None = None,
    friction_angle: Mapping[int, float] | None = None,
    dilation_angle: Mapping[int, float] | None = None,
    cohesion: Mapping[int, float] | None = None,
    name_prefix: str = "RFM",
    overwrite: bool = False,
) -> AssignmentResult:
    """Clone a source material per target element and stream an atomic output.

    The legacy modulus and density keyword arguments remain accepted. New code
    can pass all supported properties through ``property_values``.
    """
    supplied: dict[PropertyKind, Mapping[int, float]] = {}
    if property_values is not None:
        supplied.update({PropertyKind(kind): values for kind, values in property_values.items()})
    legacy = {
        PropertyKind.ELASTIC_MODULUS: youngs_modulus,
        PropertyKind.DENSITY: density,
        PropertyKind.POISSONS_RATIO: poissons_ratio,
        PropertyKind.FRICTION_ANGLE: friction_angle,
        PropertyKind.DILATION_ANGLE: dilation_angle,
        PropertyKind.COHESION: cohesion,
    }
    for kind, values in legacy.items():
        if values is None:
            continue
        if kind in supplied:
            raise UnsafeWriteError(
                f"{property_definition(kind).display_name} was supplied more than once."
            )
        supplied[kind] = values
    if not supplied:
        raise UnsafeWriteError("At least one material property must be randomized.")
    normalized = {
        kind: _validate_values(kind, values, region.eligible_labels)
        for kind, values in supplied.items()
    }
    property_maps = {kind: values for kind, values in normalized.items() if values is not None}
    source_material = model.material(region.coverage.source_material_name)
    _validate_cloneable_material(
        model,
        source_material,
        property_kinds=tuple(property_maps),
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

    section_token = model.tokens[region.coverage.section.token_index]
    section_end = _token_content_end(model, section_token)
    insertion_position = max(material.end for material in model.materials.values())

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:

            def write_text(text: str) -> None:
                temporary.write(text.encode(model.source.encoding))

            def write_materials() -> None:
                for element_label in region.eligible_labels:
                    write_text(
                        _clone_material(
                            model,
                            source_material,
                            new_name=generated_materials[element_label],
                            property_values={
                                kind: values[element_label]
                                for kind, values in property_maps.items()
                            },
                        )
                    )

            temporary.write(model.source.bom)
            if section_token.start <= insertion_position:
                write_text(model.source.text[: section_token.start])
                for chunk in section_text:
                    write_text(chunk)
                write_text(model.source.text[section_end:insertion_position])
                write_materials()
                write_text(model.source.text[insertion_position:])
            else:
                write_text(model.source.text[:insertion_position])
                write_materials()
                write_text(model.source.text[insertion_position : section_token.start])
                for chunk in section_text:
                    write_text(chunk)
                write_text(model.source.text[section_end:])
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        output_size = Path(temporary_name).stat().st_size
        with Path(temporary_name).open("rb") as completed:
            output_sha256 = hashlib.file_digest(completed, "sha256").hexdigest()
        _publish_temporary(temporary_name, destination, overwrite=overwrite)
    except (OSError, UnsafeWriteError) as exc:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        if isinstance(exc, UnsafeWriteError):
            raise
        raise UnsafeWriteError(f"Could not write generated model: {destination}") from exc

    return AssignmentResult(
        output_path=destination,
        output_sha256=output_sha256,
        output_size_bytes=output_size,
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
        randomized_properties=tuple(property_maps),
    )
