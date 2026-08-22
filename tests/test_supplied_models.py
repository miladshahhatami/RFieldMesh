"""Regression checks for the user-supplied representative models."""

from pathlib import Path

import pytest

from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import resolve_region
from rfieldmesh.application.preview import preview_model
from rfieldmesh.config.enums import DistributionKind, PropertyKind
from rfieldmesh.config.models import (
    BoundsConfig,
    CorrelationConfig,
    GenerationConfig,
    MomentSpecification,
    RandomVariableConfig,
)

MODELS = Path(__file__).resolve().parents[1] / "validation" / "representative_models"
MODEL_2D = MODELS / "2D-Model.inp"
MODEL_3D = MODELS / "3D-Model.inp"


@pytest.mark.regression
def test_supplied_2d_model_counts_and_mapping() -> None:
    model = parse_abaqus_model(MODEL_2D)
    region = resolve_region(model, part_name="Part-1", set_name="Set-1")
    assert len(region.part.node_coordinates) == 20_301
    assert len(region.selected_labels) == 20_000
    assert len(region.eligible_labels) == 20_000
    assert region.excluded_by_type == {}
    assert region.region_origin.tolist() == [0.0, 0.0]
    soil = model.material("Soil")
    assert soil.friction_angle == 25.0
    assert soil.dilation_angle == 5.0
    assert soil.cohesion == 5000.0
    assert model.material("bedrock").friction_angle is None
    assert model.material("bedrock").cohesion is None


@pytest.mark.regression
def test_supplied_2d_gui_default_cohesion_preview_uses_budget_adjustment(
    tmp_path: Path,
) -> None:
    config = GenerationConfig(
        source_path=str(MODEL_2D),
        output_path=str(tmp_path / "unused-preview.inp"),
        part_name="Part-1",
        set_name="Set-1",
        variables=(
            RandomVariableConfig(
                property_kind=PropertyKind.COHESION,
                moments=MomentSpecification(
                    mean=5000.0,
                    standard_deviation=1000.0,
                    unit_label="Pa",
                ),
                distribution=DistributionKind.TRUNCATED_NORMAL,
                correlation=CorrelationConfig(scales=(10.0, 1.0)),
                bounds=BoundsConfig(lower=0.0),
            ),
        ),
    )
    preview = preview_model(config)
    diagnostics = preview.fields[0].diagnostics
    assert preview.eligible_count == 20_000
    assert diagnostics["automatic_budget_adjustment"] is True
    assert diagnostics["effective_directional_retained_variance"] == 0.995
    assert diagnostics["coefficient_count"] <= config.spectral.max_coefficient_count


@pytest.mark.regression
def test_supplied_3d_model_mixed_layer_and_translation() -> None:
    model = parse_abaqus_model(MODEL_3D)
    region = resolve_region(
        model,
        part_name="Layered Soil Quarter",
        set_name="Layer1",
    )
    assert len(region.selected_labels) == 10_632
    assert len(region.eligible_labels) == 10_032
    assert len(region.excluded_by_type["AC3D8R"]) == 600
    assert len(region.coverage.remainder_labels) == 600
    assert region.region_origin.tolist() == pytest.approx([0.0, 0.0, -24.0])
    assert model.material("Layer1").friction_angle == 20.0
    assert model.material("Layer1").cohesion == 15_000.0
    assert model.material("Layer2").cohesion == 20_000.0
    assert model.material("Layer3").cohesion == 5_000.0
    assert model.material("Steel").friction_angle is None
    assert model.material("Steel").cohesion is None
