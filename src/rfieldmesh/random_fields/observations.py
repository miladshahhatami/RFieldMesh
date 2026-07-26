"""Observation grids and generated latent-field containers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from rfieldmesh.exceptions import ConfigurationError

FloatArray = NDArray[np.float64]


def _readonly_1d(values: ArrayLike, name: str) -> FloatArray:
    array = np.array(values, dtype=np.float64, copy=True)
    if array.ndim != 1 or array.size < 2:
        raise ConfigurationError(f"{name} must be a one-dimensional array with at least 2 nodes.")
    if not np.all(np.isfinite(array)) or np.any(np.diff(array) <= 0.0):
        raise ConfigurationError(f"{name} must contain finite, strictly increasing coordinates.")
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True)
class StructuredGrid2D:
    """Axis-aligned two-dimensional rectangular grid.

    Arrays generated on this grid use shape ``(n_x_cells, n_z_cells)``. The
    first index is the horizontal coordinate, matching the supplied MATLAB
    field and its column-major element mapping.
    """

    x_nodes: FloatArray
    z_nodes: FloatArray

    def __init__(self, x_nodes: ArrayLike, z_nodes: ArrayLike) -> None:
        object.__setattr__(self, "x_nodes", _readonly_1d(x_nodes, "x_nodes"))
        object.__setattr__(self, "z_nodes", _readonly_1d(z_nodes, "z_nodes"))

    @property
    def x_centers(self) -> FloatArray:
        return np.asarray(0.5 * (self.x_nodes[:-1] + self.x_nodes[1:]), dtype=np.float64)

    @property
    def z_centers(self) -> FloatArray:
        return np.asarray(0.5 * (self.z_nodes[:-1] + self.z_nodes[1:]), dtype=np.float64)

    @property
    def x_widths(self) -> FloatArray:
        return np.asarray(np.diff(self.x_nodes), dtype=np.float64)

    @property
    def z_widths(self) -> FloatArray:
        return np.asarray(np.diff(self.z_nodes), dtype=np.float64)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.x_nodes.size - 1, self.z_nodes.size - 1)

    @property
    def extent(self) -> tuple[float, float]:
        return (
            float(self.x_nodes[-1] - self.x_nodes[0]),
            float(self.z_nodes[-1] - self.z_nodes[0]),
        )

    def centroid_points(self) -> FloatArray:
        """Return cell centres flattened with z varying fastest."""
        x_grid, z_grid = np.meshgrid(self.x_centers, self.z_centers, indexing="ij")
        return np.column_stack((x_grid.ravel(), z_grid.ravel()))


@dataclass(frozen=True, slots=True)
class GaussianFieldRealization:
    """One zero-mean latent Gaussian realization."""

    values: FloatArray
    latent_variance: FloatArray
    diagnostics: Any
