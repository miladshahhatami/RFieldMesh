"""Regression tests for the cohesion enhancement in RFieldMesh v1.0.0."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import resolve_region
from rfieldmesh.abaqus.validation import validate_generated_output
from rfieldmesh.abaqus.writer import write_elementwise_materials
from rfieldmesh.application.batch import run_batch
from rfieldmesh.application.generate import generate_model
from rfieldmesh.application.preview import preview_model
from rfieldmesh.cli.app import app
from rfieldmesh.config.enums import DistributionKind, GenerationAlgorithm, PropertyKind
from rfieldmesh.config.models import (
    BatchConfig,
    BoundsConfig,
    CorrelationConfig,
    GenerationConfig,
    MomentSpecification,
    RandomVariableConfig,
    SpectralConfig,
)
from rfieldmesh.config.properties import property_definition, validate_property_values
from rfieldmesh.exceptions import (
    ComputationalBudgetError,
    ConfigurationError,
    UnsupportedModelError,
)
from rfieldmesh.random_fields.rng import property_stream_code, rng_for_realization
from rfieldmesh.visualization.figures import distribution_figure, field_figure

runner = CliRunner()


def _values(first: float, second: float) -> dict[int, float]:
    return {10: first, 20: second}


def _cohesion_variable(
    distribution: DistributionKind = DistributionKind.TRUNCATED_NORMAL,
) -> RandomVariableConfig:
    return RandomVariableConfig(
        property_kind=PropertyKind.COHESION,
        moments=MomentSpecification(
            mean=5000.0,
            standard_deviation=500.0,
            unit_label="Pa",
        ),
        distribution=distribution,
        correlation=CorrelationConfig(scales=(2.0, 1.0)),
        bounds=(
            BoundsConfig(lower=0.0) if distribution is DistributionKind.TRUNCATED_NORMAL else None
        ),
    )


def _cohesion_generation(source: Path, output: Path) -> GenerationConfig:
    return GenerationConfig(
        source_path=str(source),
        output_path=str(output),
        part_name="Soil Part",
        set_name="Target",
        variables=(_cohesion_variable(),),
        algorithm=GenerationAlgorithm.COVARIANCE_KL,
    )


def test_cohesion_registry_mapping_and_constraints() -> None:
    definition = property_definition(PropertyKind.COHESION)
    assert definition.abaqus_keyword == "mohr coulomb hardening"
    assert definition.column_index == 0
    assert definition.value_is_valid(0.0)
    assert not definition.value_is_valid(-1.0e-12)
    assert property_stream_code(PropertyKind.COHESION) == 601


def test_parser_reads_first_hardening_value_as_cohesion(small_inp: Path) -> None:
    material = parse_abaqus_model(small_inp).material("Soil")
    assert material.cohesion == 5000.0
    assert material.property_value(PropertyKind.COHESION) == 5000.0


def test_writer_updates_cohesion_and_preserves_hardening_companion(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    model = parse_abaqus_model(small_inp)
    region = resolve_region(model, part_name="Soil Part", set_name="Target")
    values = _values(4200.0, 6100.0)
    result = write_elementwise_materials(
        model,
        region,
        tmp_path / "cohesion.inp",
        cohesion=values,
    )
    validation = validate_generated_output(result, expected_cohesion=values)
    assert validation.checked_properties == ("cohesion",)
    generated = parse_abaqus_model(result.output_path)
    for label, material_name in result.generated_material_names.items():
        assert generated.material(material_name).cohesion == values[label]
    generated_text = result.output_path.read_text(encoding="ascii")
    assert "4200, 0." in generated_text
    assert "6100, 0." in generated_text
    assert generated_text.count("*Damping, alpha=0.1, beta=0.01") == 3
    assert generated_text.count("*Mohr Coulomb\n25., 5.\n") == 3


def test_writer_updates_and_verifies_all_six_properties(
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
        PropertyKind.COHESION: _values(4200.0, 6100.0),
    }
    result = write_elementwise_materials(
        model,
        region,
        tmp_path / "all_six.inp",
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
    assert first.cohesion == 4200.0


def test_cohesion_must_be_nonnegative_without_clipping() -> None:
    with pytest.raises(ConfigurationError, match="not clipped"):
        validate_property_values(PropertyKind.COHESION, np.array([5000.0, -0.01]))
    with pytest.raises(ValidationError, match="Cohesion"):
        RandomVariableConfig(
            property_kind=PropertyKind.COHESION,
            moments=MomentSpecification(mean=-1.0, standard_deviation=1.0),
            distribution=DistributionKind.TRUNCATED_NORMAL,
            correlation=CorrelationConfig(scales=(2.0, 1.0)),
            bounds=BoundsConfig(lower=0.0),
        )


@pytest.mark.parametrize("distribution", tuple(DistributionKind))
def test_cohesion_generates_with_all_supported_marginals(
    distribution: DistributionKind,
    small_inp: Path,
    tmp_path: Path,
) -> None:
    variable = _cohesion_variable(distribution)
    assert variable.distribution is distribution
    config = _cohesion_generation(small_inp, tmp_path / f"{distribution.value}.inp").model_copy(
        update={"variables": (variable,)}
    )
    preview = preview_model(config)
    assert min(preview.fields[0].values.values()) >= 0.0


def test_cohesion_api_preview_manifest_and_source_preservation(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    source_hash = hashlib.sha256(small_inp.read_bytes()).hexdigest()
    config = _cohesion_generation(small_inp, tmp_path / "api_cohesion.inp")
    first_preview = preview_model(config)
    second_preview = preview_model(config)
    assert np.array_equal(first_preview.fields[0].values, second_preview.fields[0].values)
    assert first_preview.fields[0].property_kind is PropertyKind.COHESION
    assert field_figure(first_preview, PropertyKind.COHESION).data[0].type == "heatmap"
    assert {trace.type for trace in distribution_figure(first_preview).data} == {
        "histogram",
        "scatter",
    }

    result = generate_model(config)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.validation.checked_properties == ("cohesion",)
    assert manifest["fields"][0]["property_kind"] == "cohesion"
    assert manifest["fields"][0]["abaqus_keyword"] == "mohr coulomb hardening"
    assert manifest["configuration"]["variables"][0]["bounds"]["lower"] == 0.0
    assert manifest["fields"][0]["statistics"]["minimum"] >= 0.0
    assert manifest["validation"]["checked_properties"] == ["cohesion"]
    assert hashlib.sha256(small_inp.read_bytes()).hexdigest() == source_hash


def test_auto_spectral_budget_adjustment_supports_gui_default_cohesion(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    config = GenerationConfig(
        source_path=str(small_inp),
        output_path=str(tmp_path / "auto_cohesion.inp"),
        part_name="Soil Part",
        set_name="Target",
        variables=(
            _cohesion_variable().model_copy(
                update={"correlation": CorrelationConfig(scales=(2.0, 1.0))}
            ),
        ),
        spectral=SpectralConfig(
            max_mode_cap=512,
            max_coefficient_count=200_000,
        ),
    )
    preview = preview_model(config)
    diagnostics = preview.fields[0].diagnostics
    assert diagnostics["requested_directional_retained_variance"] == 0.99999
    assert diagnostics["effective_directional_retained_variance"] == 0.995
    assert diagnostics["automatic_budget_adjustment"] is True
    assert min(preview.fields[0].values.values()) >= 0.0

    strict_config = config.model_copy(update={"algorithm": GenerationAlgorithm.SPECTRAL})
    with pytest.raises(ComputationalBudgetError):
        preview_model(strict_config)

    correlation = CorrelationConfig(scales=(10.0, 1.0))
    all_six = (
        RandomVariableConfig(
            property_kind=PropertyKind.ELASTIC_MODULUS,
            moments=MomentSpecification(mean=2.0e7, standard_deviation=6.0e6),
            distribution=DistributionKind.LOGNORMAL,
            correlation=correlation,
        ),
        RandomVariableConfig(
            property_kind=PropertyKind.DENSITY,
            moments=MomentSpecification(mean=1800.0, standard_deviation=180.0),
            distribution=DistributionKind.LOGNORMAL,
            correlation=correlation,
        ),
        RandomVariableConfig(
            property_kind=PropertyKind.POISSONS_RATIO,
            moments=MomentSpecification(mean=0.35, standard_deviation=0.028),
            distribution=DistributionKind.TRUNCATED_NORMAL,
            correlation=correlation,
            bounds=BoundsConfig(lower=0.05, upper=0.49),
        ),
        RandomVariableConfig(
            property_kind=PropertyKind.FRICTION_ANGLE,
            moments=MomentSpecification(mean=25.0, standard_deviation=2.5),
            distribution=DistributionKind.TRUNCATED_NORMAL,
            correlation=correlation,
            bounds=BoundsConfig(lower=10.0, upper=45.0),
        ),
        RandomVariableConfig(
            property_kind=PropertyKind.DILATION_ANGLE,
            moments=MomentSpecification(mean=5.0, standard_deviation=1.0),
            distribution=DistributionKind.TRUNCATED_NORMAL,
            correlation=correlation,
            bounds=BoundsConfig(lower=0.0, upper=15.0),
        ),
        _cohesion_variable().model_copy(update={"correlation": correlation}),
    )
    all_six_preview = preview_model(config.model_copy(update={"variables": all_six}))
    assert tuple(field.property_kind for field in all_six_preview.fields) == tuple(PropertyKind)
    assert all(
        not field.diagnostics["automatic_budget_adjustment"] for field in all_six_preview.fields[:2]
    )
    assert all(
        field.diagnostics["automatic_budget_adjustment"] for field in all_six_preview.fields[2:]
    )


def test_cli_generates_cohesion_field(small_inp: Path) -> None:
    project = small_inp.parent / "cohesion_project.json"
    payload = _cohesion_generation(small_inp, small_inp.parent / "cli_cohesion.inp").model_dump(
        mode="json"
    )
    payload["source_path"] = small_inp.name
    payload["output_path"] = "cli_cohesion.inp"
    project.write_text(json.dumps(payload), encoding="utf-8")
    result = runner.invoke(app, ["generate", str(project)])
    assert result.exit_code == 0, result.stdout
    generated = parse_abaqus_model(small_inp.parent / "cli_cohesion.inp")
    assert generated.material("RFM_M_10").cohesion is not None
    assert "Validated elements: 2" in result.stdout


def test_batch_generates_reproducible_cohesion_realizations(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    config = BatchConfig(
        generation=_cohesion_generation(small_inp, tmp_path / "ignored.inp"),
        output_directory=str(tmp_path / "cohesion_batch"),
        realization_count=2,
        filename_template="cohesion_{index}.inp",
    )
    result = run_batch(config)
    assert result.completed_count == 2
    assert result.failed_count == 0
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["items"][0]["status"] == "completed"
    assert all(Path(item.output_path).is_file() for item in result.items)


@pytest.mark.parametrize(
    ("replacement", "match"),
    [
        ("", "will not be introduced"),
        (
            "*Mohr Coulomb Hardening, dependencies=1\n5000., 0., 1.\n",
            "without temperature, field, or dependency",
        ),
        (
            "*Mohr Coulomb Hardening\n5000., 0.\n6000., 0.1\n",
            "one-row scalar",
        ),
        (
            "*Mohr Coulomb Hardening\n5000., 0.\n*Mohr Coulomb Hardening\n6000., 0.\n",
            "exactly one unambiguous",
        ),
    ],
)
def test_cohesion_writer_fails_closed_for_unsupported_hardening_cards(
    small_inp: Path,
    tmp_path: Path,
    replacement: str,
    match: str,
) -> None:
    original = "*Mohr Coulomb Hardening\n5000., 0.\n"
    source = tmp_path / "unsupported.inp"
    content = small_inp.read_text(encoding="ascii").replace(original, replacement)
    source.write_text(content, encoding="ascii", newline="")
    model = parse_abaqus_model(source)
    region = resolve_region(model, part_name="Soil Part", set_name="Target")
    with pytest.raises(UnsupportedModelError, match=match):
        write_elementwise_materials(
            model,
            region,
            tmp_path / "should_not_exist.inp",
            property_values={PropertyKind.COHESION: _values(4200.0, 6100.0)},
        )


def test_existing_property_rng_streams_are_unchanged() -> None:
    expected = {
        PropertyKind.ELASTIC_MODULUS: np.array(
            [
                -0.021531842184665268,
                0.8975051519226498,
                -0.9590253979812179,
                -0.7786868450178202,
                -0.460891232887945,
                -1.2462453664734021,
                -0.778099610455781,
                -0.11691126043910842,
            ]
        ),
        PropertyKind.DENSITY: np.array(
            [
                1.1111079637025947,
                1.3715082916230983,
                -1.0467335406660623,
                -1.3531848328698697,
                -0.4359189413327042,
                0.625289342866539,
                1.1811167397836733,
                -0.10296919655653378,
            ]
        ),
        PropertyKind.POISSONS_RATIO: np.array(
            [
                -0.0779186808606398,
                -0.4966421789742425,
                0.33620486814525957,
                0.5317844541557273,
                -1.44062020542743,
                0.4109299133879819,
                1.7204451701446275,
                -0.6938212502062431,
            ]
        ),
        PropertyKind.FRICTION_ANGLE: np.array(
            [
                -0.11326744882969819,
                0.8974234357095495,
                2.2791152477239294,
                -0.0010785991041194266,
                -0.6152914428769752,
                -0.17691372825587082,
                0.6786913250218595,
                2.365593469875718,
            ]
        ),
        PropertyKind.DILATION_ANGLE: np.array(
            [
                0.5913993798895164,
                -2.615382341498163,
                -0.1968853202807528,
                0.15889095485539584,
                -0.5700251879109428,
                0.01429831275772136,
                2.3475812899951025,
                0.6211817753793174,
            ]
        ),
    }
    for kind, expected_sample in expected.items():
        sample = rng_for_realization(1403, 4, kind).standard_normal(8)
        assert np.array_equal(sample, expected_sample)
    cohesion_sample = rng_for_realization(1403, 4, PropertyKind.COHESION).standard_normal(8)
    assert all(not np.array_equal(cohesion_sample, sample) for sample in expected.values())
