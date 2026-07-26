"""Semantic parser, eligibility, transformation, and geometry tests."""

from pathlib import Path

import numpy as np

from rfieldmesh.abaqus.geometry import structured_region_2d
from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import resolve_region


def test_parser_resolves_semantic_model(small_inp: Path) -> None:
    model = parse_abaqus_model(small_inp)
    part = model.part("soil part")
    material = model.material("SOIL")
    assert len(part.node_coordinates) == 8
    assert len(part.elements) == 3
    assert part.element_set("target").labels == (10, 20)
    assert material.density == 1800.0
    assert material.youngs_modulus == 2.0e7
    assert material.poissons_ratio == 0.35


def test_region_resolves_instance_coordinates_and_section_remainder(
    small_inp: Path,
) -> None:
    model = parse_abaqus_model(small_inp)
    region = resolve_region(
        model,
        part_name="Soil Part",
        set_name="Target",
        instance_name="Soil Part-1",
    )
    np.testing.assert_allclose(region.assembly_coordinates, [[10.5, 20.5], [11.5, 20.5]])
    np.testing.assert_allclose(region.representative_coordinates, [[0.5, 0.5], [1.5, 0.5]])
    assert region.eligible_labels == (10, 20)
    assert region.coverage.source_material_name == "Soil"
    assert region.coverage.remainder_labels == (30,)


def test_structured_grid_maps_cells_to_element_labels(small_inp: Path) -> None:
    region = resolve_region(
        parse_abaqus_model(small_inp),
        part_name="Soil Part",
        set_name="Target",
    )
    structured = structured_region_2d(region)
    assert structured.grid.shape == (2, 1)
    np.testing.assert_array_equal(structured.labels, [[10], [20]])
