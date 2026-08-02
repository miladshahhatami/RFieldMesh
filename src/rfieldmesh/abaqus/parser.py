"""Semantic parser for the Abaqus concepts required by RFieldMesh."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from rfieldmesh.abaqus.element_registry import element_descriptor
from rfieldmesh.abaqus.model import (
    AbaqusModel,
    ElementRecord,
    ElementSet,
    Instance,
    InstanceTransform,
    MaterialDefinition,
    Part,
    SolidSection,
)
from rfieldmesh.abaqus.source import AbaqusSource
from rfieldmesh.abaqus.tokenizer import tokenize
from rfieldmesh.abaqus.tokens import KeywordToken, canonical_name
from rfieldmesh.exceptions import AbaqusParseError, UnsupportedModelError

_MATERIAL_TERMINATORS = {
    "amplitude",
    "assembly",
    "boundary",
    "contact pair",
    "element",
    "elset",
    "end assembly",
    "end instance",
    "end part",
    "heading",
    "include",
    "initial conditions",
    "instance",
    "material",
    "node",
    "nset",
    "part",
    "preprint",
    "solid section",
    "step",
    "surface",
    "surface interaction",
}


def _data_lines(source: AbaqusSource, token: KeywordToken) -> list[str]:
    lines: list[str] = []
    for line in source.text[token.data_start : token.data_end].splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("**"):
            lines.append(stripped)
    return lines


def _csv_fields(line: str) -> list[str]:
    return [field.strip() for field in line.split(",") if field.strip()]


def _require_parameter(token: KeywordToken, name: str) -> str:
    value = token.parameter(name)
    if value is None:
        raise AbaqusParseError(
            f"*{token.raw_keyword} at character {token.start} requires parameter {name!r}."
        )
    return value


def _parse_nodes(source: AbaqusSource, token: KeywordToken, part: Part) -> None:
    for line in _data_lines(source, token):
        fields = _csv_fields(line)
        if len(fields) < 3:
            raise AbaqusParseError(f"Invalid *Node data row: {line!r}")
        try:
            label = int(fields[0])
            coordinates = tuple(float(value) for value in fields[1:])
        except ValueError as exc:
            raise AbaqusParseError(f"Invalid *Node data row: {line!r}") from exc
        if label in part.node_coordinates:
            raise AbaqusParseError(f"Duplicate node label {label} in part {part.name!r}.")
        if len(coordinates) not in (2, 3) or any(not math.isfinite(v) for v in coordinates):
            raise AbaqusParseError(f"Node {label} has invalid coordinates.")
        part.node_coordinates[label] = coordinates


def _parse_elements(source: AbaqusSource, token: KeywordToken, part: Part) -> None:
    element_type = _require_parameter(token, "type").upper()
    descriptor = element_descriptor(element_type)
    for line in _data_lines(source, token):
        fields = _csv_fields(line)
        if len(fields) < 2:
            raise AbaqusParseError(f"Invalid *Element data row: {line!r}")
        try:
            label = int(fields[0])
            connectivity = tuple(int(value) for value in fields[1:])
        except ValueError as exc:
            raise AbaqusParseError(f"Invalid *Element data row: {line!r}") from exc
        if descriptor.supported and len(connectivity) != descriptor.node_count:
            raise UnsupportedModelError(
                f"Element {label} of type {element_type} has {len(connectivity)} nodes; "
                f"{descriptor.node_count} were expected."
            )
        if label in part.elements:
            raise AbaqusParseError(f"Duplicate element label {label} in part {part.name!r}.")
        part.elements[label] = ElementRecord(
            label=label,
            element_type=element_type,
            connectivity=connectivity,
        )


def _parse_elset(source: AbaqusSource, token: KeywordToken, part: Part) -> None:
    name = _require_parameter(token, "elset")
    raw_fields = [field for line in _data_lines(source, token) for field in _csv_fields(line)]
    labels: list[int] = []
    if token.parameter("generate") is None and "generate" not in token.parameters:
        try:
            labels = [int(value) for value in raw_fields]
        except ValueError as exc:
            raise UnsupportedModelError(
                f"Element set {name!r} contains a set reference; Phase 4 accepts explicit "
                "integer labels and GENERATE ranges."
            ) from exc
    else:
        if len(raw_fields) % 3:
            raise AbaqusParseError(f"GENERATE set {name!r} must contain triples.")
        for index in range(0, len(raw_fields), 3):
            start, stop, step = (int(value) for value in raw_fields[index : index + 3])
            if step <= 0 or stop < start:
                raise AbaqusParseError(f"Invalid GENERATE range in set {name!r}.")
            labels.extend(range(start, stop + 1, step))
    unique_labels = tuple(dict.fromkeys(labels))
    key = canonical_name(name)
    if key in part.element_sets:
        raise UnsupportedModelError(
            f"Repeated definitions of element set {name!r} are not yet merged safely."
        )
    part.element_sets[key] = ElementSet(
        name=name,
        labels=unique_labels,
        token_index=token.index,
    )


def _axis_angle_matrix(values: list[float]) -> np.ndarray:
    point_a = np.asarray(values[:3], dtype=np.float64)
    point_b = np.asarray(values[3:6], dtype=np.float64)
    angle = math.radians(values[6])
    axis = point_b - point_a
    norm = float(np.linalg.norm(axis))
    if norm <= 0.0:
        raise AbaqusParseError("Instance rotation axis must have nonzero length.")
    x, y, z = axis / norm
    cosine = math.cos(angle)
    sine = math.sin(angle)
    complement = 1.0 - cosine
    rotation = np.array(
        [
            [
                cosine + x * x * complement,
                x * y * complement - z * sine,
                x * z * complement + y * sine,
            ],
            [
                y * x * complement + z * sine,
                cosine + y * y * complement,
                y * z * complement - x * sine,
            ],
            [
                z * x * complement - y * sine,
                z * y * complement + x * sine,
                cosine + z * z * complement,
            ],
        ],
        dtype=np.float64,
    )
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = point_a - rotation @ point_a
    return matrix


def _parse_instance_transform(source: AbaqusSource, token: KeywordToken) -> InstanceTransform:
    rows = _data_lines(source, token)
    matrix = np.eye(4, dtype=np.float64)
    if not rows:
        return InstanceTransform(matrix=matrix)
    try:
        translation = [float(value) for value in _csv_fields(rows[0])]
    except ValueError as exc:
        raise AbaqusParseError("Instance transformation contains nonnumeric data.") from exc
    if len(translation) != 3:
        raise UnsupportedModelError("Instance translation must contain exactly three values.")
    matrix[:3, 3] = translation
    if len(rows) > 1:
        try:
            rotation = [float(value) for value in _csv_fields(rows[1])]
        except ValueError as exc:
            raise AbaqusParseError("Instance rotation contains nonnumeric data.") from exc
        if len(rotation) != 7:
            raise UnsupportedModelError("Instance rotation must contain seven values.")
        matrix = _axis_angle_matrix(rotation) @ matrix
    if len(rows) > 2:
        raise UnsupportedModelError("More than two instance transformation rows were found.")
    return InstanceTransform(matrix=matrix)


def _first_numeric_row(source: AbaqusSource, token: KeywordToken) -> list[float]:
    rows = _data_lines(source, token)
    if not rows:
        raise AbaqusParseError(f"*{token.raw_keyword} has no property data.")
    try:
        return [float(value) for value in _csv_fields(rows[0])]
    except ValueError as exc:
        raise AbaqusParseError(f"*{token.raw_keyword} contains nonnumeric property data.") from exc


def _semantic_token_end(source: AbaqusSource, token: KeywordToken) -> int:
    """Exclude trailing comments belonging to the following model section."""
    offset = token.data_start
    for line in source.text[token.data_start : token.data_end].splitlines(keepends=True):
        if line.lstrip().startswith("**"):
            return offset
        offset += len(line)
    return token.data_end


def _parse_materials(
    source: AbaqusSource,
    tokens: tuple[KeywordToken, ...],
) -> dict[str, MaterialDefinition]:
    definitions: dict[str, MaterialDefinition] = {}
    for position, token in enumerate(tokens):
        if token.keyword != "material":
            continue
        name = _require_parameter(token, "name")
        child_tokens: list[KeywordToken] = []
        candidate_position = position + 1
        while candidate_position < len(tokens):
            candidate = tokens[candidate_position]
            if candidate.keyword in _MATERIAL_TERMINATORS:
                break
            child_tokens.append(candidate)
            candidate_position += 1
        density_token = next(
            (candidate for candidate in child_tokens if candidate.keyword == "density"),
            None,
        )
        elastic_token = next(
            (candidate for candidate in child_tokens if candidate.keyword == "elastic"),
            None,
        )
        mohr_coulomb_token = next(
            (candidate for candidate in child_tokens if candidate.keyword == "mohr coulomb"),
            None,
        )
        density = None
        youngs_modulus = None
        poissons_ratio = None
        friction_angle = None
        dilation_angle = None
        if density_token is not None:
            density_values = _first_numeric_row(source, density_token)
            density = density_values[0]
        if elastic_token is not None:
            elastic_values = _first_numeric_row(source, elastic_token)
            if len(elastic_values) < 2:
                raise UnsupportedModelError(
                    f"Material {name!r} does not contain isotropic E and Poisson ratio."
                )
            youngs_modulus, poissons_ratio = elastic_values[:2]
        if mohr_coulomb_token is not None:
            mohr_coulomb_values = _first_numeric_row(source, mohr_coulomb_token)
            if len(mohr_coulomb_values) < 2:
                raise UnsupportedModelError(
                    f"Material {name!r} does not contain scalar friction and dilation angles."
                )
            friction_angle, dilation_angle = mohr_coulomb_values[:2]
        final_token = child_tokens[-1] if child_tokens else token
        definition = MaterialDefinition(
            name=name,
            start=token.start,
            end=_semantic_token_end(source, final_token),
            material_token_index=token.index,
            density_token_index=None if density_token is None else density_token.index,
            elastic_token_index=None if elastic_token is None else elastic_token.index,
            mohr_coulomb_token_index=(
                None if mohr_coulomb_token is None else mohr_coulomb_token.index
            ),
            density=density,
            youngs_modulus=youngs_modulus,
            poissons_ratio=poissons_ratio,
            friction_angle=friction_angle,
            dilation_angle=dilation_angle,
        )
        key = canonical_name(name)
        if key in definitions:
            raise AbaqusParseError(f"Duplicate material name {name!r}.")
        definitions[key] = definition
    return definitions


def parse_abaqus_model(path: str | Path) -> AbaqusModel:
    """Parse an Abaqus input file into a source-preserving semantic model."""
    source = AbaqusSource.read(path)
    tokens = tokenize(source)
    parts: dict[str, Part] = {}
    instances: dict[str, Instance] = {}
    include_paths: list[Path] = []
    current_part: Part | None = None
    in_assembly = False

    for token in tokens:
        if token.keyword == "part":
            name = _require_parameter(token, "name")
            key = canonical_name(name)
            if key in parts:
                raise AbaqusParseError(f"Duplicate part name {name!r}.")
            current_part = Part(name=name)
            parts[key] = current_part
        elif token.keyword == "end part":
            current_part = None
        elif token.keyword == "assembly":
            in_assembly = True
        elif token.keyword == "end assembly":
            in_assembly = False
        elif token.keyword == "node" and current_part is not None:
            _parse_nodes(source, token, current_part)
        elif token.keyword == "element" and current_part is not None:
            _parse_elements(source, token, current_part)
        elif token.keyword == "elset" and current_part is not None:
            _parse_elset(source, token, current_part)
        elif token.keyword == "solid section" and current_part is not None:
            current_part.sections.append(
                SolidSection(
                    elset_name=_require_parameter(token, "elset"),
                    material_name=_require_parameter(token, "material"),
                    token_index=token.index,
                )
            )
        elif token.keyword == "instance" and in_assembly:
            name = _require_parameter(token, "name")
            part_name = _require_parameter(token, "part")
            key = canonical_name(name)
            if key in instances:
                raise AbaqusParseError(f"Duplicate instance name {name!r}.")
            instances[key] = Instance(
                name=name,
                part_name=part_name,
                transform=_parse_instance_transform(source, token),
                token_index=token.index,
            )
        elif token.keyword == "include":
            include_name = token.parameter("input") or token.parameter("file")
            if include_name is None:
                raise AbaqusParseError("*Include requires INPUT= or FILE=.")
            include_paths.append((source.path.parent / include_name).resolve())

    for instance in instances.values():
        if canonical_name(instance.part_name) not in parts:
            raise AbaqusParseError(
                f"Instance {instance.name!r} refers to missing part {instance.part_name!r}."
            )

    return AbaqusModel(
        source=source,
        tokens=tokens,
        parts=parts,
        instances=instances,
        materials=_parse_materials(source, tokens),
        include_paths=tuple(include_paths),
    )
