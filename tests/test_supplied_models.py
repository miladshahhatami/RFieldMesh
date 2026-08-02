"""Regression checks for the user-supplied representative models."""

from pathlib import Path

import pytest

from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import resolve_region

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
    assert model.material("bedrock").friction_angle is None


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
    assert model.material("Steel").friction_angle is None
