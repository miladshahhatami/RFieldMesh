"""Mesh-geometry adapters used by random-field algorithms."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from rfieldmesh.abaqus.regions import ResolvedRegion
from rfieldmesh.exceptions import GeometryError
from rfieldmesh.random_fields.observations import StructuredGrid2D

IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class StructuredRegion2D:
    """A complete axis-aligned quadrilateral grid and its element-label mapping."""

    grid: StructuredGrid2D
    labels: IntArray


def _assembly_element_points(region: ResolvedRegion, label: int) -> NDArray[np.float64]:
    element = region.part.elements[label]
    coordinates = np.asarray(
        [region.part.node_coordinates[node] for node in element.connectivity],
        dtype=np.float64,
    )
    if region.instance is not None:
        coordinates = region.instance.transform.apply(coordinates)
    return np.asarray(coordinates - region.region_origin, dtype=np.float64)


def structured_region_2d(
    region: ResolvedRegion,
    *,
    tolerance: float = 1.0e-9,
) -> StructuredRegion2D:
    """Recognize a complete axis-aligned grid of four-node continuum elements."""
    if region.dimension != 2:
        raise GeometryError("Structured spectral mapping requires a two-dimensional region.")
    bounds: dict[int, tuple[float, float, float, float]] = {}
    x_values: list[float] = []
    z_values: list[float] = []
    for label in region.eligible_labels:
        element = region.part.elements[label]
        if len(element.connectivity) != 4:
            raise GeometryError("Structured spectral mapping requires four-node elements.")
        points = _assembly_element_points(region, label)
        minimum = np.min(points, axis=0)
        maximum = np.max(points, axis=0)
        expected = {
            (minimum[0], minimum[1]),
            (minimum[0], maximum[1]),
            (maximum[0], minimum[1]),
            (maximum[0], maximum[1]),
        }
        actual = {(point[0], point[1]) for point in points}
        if len(actual) != 4 or any(
            not any(
                np.allclose(actual_point, expected_point, rtol=0.0, atol=tolerance)
                for expected_point in expected
            )
            for actual_point in actual
        ):
            raise GeometryError(
                f"Element {label} is not an axis-aligned rectangular quadrilateral."
            )
        bounds[label] = (minimum[0], maximum[0], minimum[1], maximum[1])
        x_values.extend((minimum[0], maximum[0]))
        z_values.extend((minimum[1], maximum[1]))

    x_nodes = np.unique(np.round(np.asarray(x_values) / tolerance) * tolerance)
    z_nodes = np.unique(np.round(np.asarray(z_values) / tolerance) * tolerance)
    expected_count = (x_nodes.size - 1) * (z_nodes.size - 1)
    if expected_count != len(region.eligible_labels):
        raise GeometryError("The eligible region does not form one complete rectangular grid.")
    labels = np.full((x_nodes.size - 1, z_nodes.size - 1), -1, dtype=np.int64)
    for label, (x_min, x_max, z_min, z_max) in bounds.items():
        ix = int(np.argmin(np.abs(x_nodes - x_min)))
        iz = int(np.argmin(np.abs(z_nodes - z_min)))
        if not np.isclose(x_nodes[ix + 1], x_max, rtol=0.0, atol=tolerance):
            raise GeometryError("An element spans more than one structured-grid x interval.")
        if not np.isclose(z_nodes[iz + 1], z_max, rtol=0.0, atol=tolerance):
            raise GeometryError("An element spans more than one structured-grid z interval.")
        if labels[ix, iz] != -1:
            raise GeometryError("Two elements occupy the same structured-grid cell.")
        labels[ix, iz] = label
    if np.any(labels < 0):
        raise GeometryError("The recognized structured grid contains an unassigned cell.")
    return StructuredRegion2D(
        grid=StructuredGrid2D(x_nodes=x_nodes, z_nodes=z_nodes),
        labels=labels,
    )
