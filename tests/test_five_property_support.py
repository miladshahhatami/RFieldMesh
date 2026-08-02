"""Regression tests for the five-property v1.0.0 enhancement."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import resolve_region
from rfieldmesh.abaqus.validation import validate_generated_output
from rfieldmesh.abaqus.writer import write_elementwise_materials
from rfieldmesh.config.enums import DistributionKind, PropertyKind
from rfieldmesh.config.models import (
    CorrelationConfig,
    MomentSpecification,
    RandomVariableConfig,
)
from rfieldmesh.exceptions import UnsupportedModelError
from rfieldmesh.random_fields.rng import rng_for_realization


def _values(first: float, second: float) -> dict[int, float]:
    return {10: first, 20: second}


def test_parser_reads_all_five_properties(small_inp: Path) -> None:
    material = parse_abaqus_model(small_inp).material("Soil")
    assert material.youngs_modulus == 2.0e7
    assert material.density == 1800.0
    assert material.poissons_ratio == 0.35
    assert material.friction_angle == 25.0
    assert material.dilation_angle == 5.0


def test_writer_updates_and_verifies_all_five_properties(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    model = parse_abaqus_model(small_inp)
    region = resolve_region(model, part_name="Soil Part", set_name="Target")
    values = {
        PropertyKind.ELASTIC_MODULUS: _values(1.8e7, 2.2e7),
        PropertyKind.DENSITY: _values(1750.0, 1850.0),
        PropertyKind.POISSONS_RATIO: _values(0.31, 0.37),
        PropertyKind.FRICTION_ANGLE: _values(22.0, 28.0),
        PropertyKind.DILATION_ANGLE: _values(3.0, 7.0),
    }
    result = write_elementwise_materials(
        model,
        region,
        tmp_path / "all_five.inp",
        property_values=values,
    )
    validation = validate_generated_output(result, expected_properties=values)
    assert validation.checked_properties == tuple(kind.value for kind in values)
    generated = parse_abaqus_model(result.output_path)
    first = generated.material(result.generated_material_names[10])
    assert first.youngs_modulus == 1.8e7
    assert first.density == 1750.0
    assert first.poissons_ratio == 0.31
    assert first.friction_angle == 22.0
    assert first.dilation_angle == 3.0


@pytest.mark.parametrize(
    ("kind", "values", "preserved_kind", "preserved_value"),
    [
        (PropertyKind.ELASTIC_MODULUS, _values(1.9e7, 2.1e7), PropertyKind.POISSONS_RATIO, 0.35),
        (PropertyKind.POISSONS_RATIO, _values(0.30, 0.40), PropertyKind.ELASTIC_MODULUS, 2.0e7),
        (PropertyKind.FRICTION_ANGLE, _values(20.0, 30.0), PropertyKind.DILATION_ANGLE, 5.0),
        (PropertyKind.DILATION_ANGLE, _values(2.0, 8.0), PropertyKind.FRICTION_ANGLE, 25.0),
    ],
)
def test_shared_keyword_companion_is_preserved(
    small_inp: Path,
    tmp_path: Path,
    kind: PropertyKind,
    values: dict[int, float],
    preserved_kind: PropertyKind,
    preserved_value: float,
) -> None:
    model = parse_abaqus_model(small_inp)
    region = resolve_region(model, part_name="Soil Part", set_name="Target")
    result = write_elementwise_materials(
        model,
        region,
        tmp_path / f"{kind.value}.inp",
        property_values={kind: values},
    )
    validation = validate_generated_output(result, expected_properties={kind: values})
    assert preserved_kind.value in validation.preserved_properties
    generated = parse_abaqus_model(result.output_path)
    for material_name in result.generated_material_names.values():
        assert generated.material(material_name).property_value(preserved_kind) == preserved_value


def test_mohr_coulomb_is_required_for_angle_randomization(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    content = small_inp.read_text(encoding="ascii")
    content = content.replace("*Mohr Coulomb\n25., 5.\n", "")
    source = tmp_path / "elastic_only.inp"
    source.write_text(content, encoding="ascii", newline="")
    model = parse_abaqus_model(source)
    region = resolve_region(model, part_name="Soil Part", set_name="Target")
    with pytest.raises(UnsupportedModelError, match="will not be introduced"):
        write_elementwise_materials(
            model,
            region,
            tmp_path / "invalid.inp",
            property_values={PropertyKind.FRICTION_ANGLE: _values(20.0, 30.0)},
        )


def test_legacy_modulus_identifier_is_accepted() -> None:
    variable = RandomVariableConfig.model_validate(
        {
            "property_kind": "youngs_modulus",
            "moments": {"mean": 2.0e7, "standard_deviation": 2.0e6},
            "distribution": "lognormal",
            "correlation": {"scales": [2.0, 1.0]},
        }
    )
    assert variable.property_kind is PropertyKind.ELASTIC_MODULUS
    assert variable.model_dump(mode="json")["property_kind"] == "elastic_modulus"


def test_invalid_poissons_ratio_mean_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Poisson"):
        RandomVariableConfig(
            property_kind=PropertyKind.POISSONS_RATIO,
            moments=MomentSpecification(mean=0.55, standard_deviation=0.01),
            distribution=DistributionKind.NORMAL,
            correlation=CorrelationConfig(scales=(2.0, 1.0)),
        )


def test_property_streams_are_stable_and_distinct() -> None:
    samples = [rng_for_realization(1403, 4, kind).standard_normal(16) for kind in PropertyKind]
    assert all(
        not np.array_equal(samples[left], samples[right])
        for left in range(len(samples))
        for right in range(left + 1, len(samples))
    )
