"""Regression checks for the user-supplied representative models."""

from pathlib import Path

import pytest

from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import resolve_region

UPLOAD = Path(__file__).resolve().parents[2] / "upload"
MODEL_2D = UPLOAD / "Job-1.inp"
MODEL_3D = UPLOAD / "Representative_3D_Model.inp"

pytestmark = pytest.mark.skipif(
    not MODEL_2D.exists() or not MODEL_3D.exists(),
    reason="Private supplied-model fixtures are not distributed with the package.",
)


@pytest.mark.regression
def test_supplied_2d_model_counts_and_mapping() -> None:
    model = parse_abaqus_model(MODEL_2D)
    region = resolve_region(model, part_name="Part-1", set_name="Set-1")
    assert len(region.part.node_coordinates) == 20_301
    assert len(region.selected_labels) == 20_000
    assert len(region.eligible_labels) == 20_000
    assert region.excluded_by_type == {}
    assert region.region_origin.tolist() == [0.0, 0.0]


@pytest.mark.regression
def test_supplied_3d_model_mixed_layer_and_translation() -> None:
    model = parse_abaqus_model(MODEL_3D)
    region = resolve_region(
        model,
        part_name="Layered Soil Quarter",
        set_name="Layer1",
    )
    assert len(region.selected_labels) == 138
    assert len(region.eligible_labels) == 108
    assert len(region.excluded_by_type["AC3D8R"]) == 30
    assert len(region.coverage.remainder_labels) == 30
    assert region.region_origin.tolist() == pytest.approx([0.0, 0.0, -24.0])
