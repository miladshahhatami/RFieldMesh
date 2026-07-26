"""Autocorrelation functions and analytical local-average factors."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.distance import cdist

from rfieldmesh.config.enums import CorrelationKind
from rfieldmesh.exceptions import ConfigurationError

FloatArray = NDArray[np.float64]


def _validated_scales(scales: tuple[float, ...], dimension: int) -> FloatArray:
    if len(scales) != dimension:
        raise ConfigurationError(
            f"Received {len(scales)} scales for a {dimension}-dimensional coordinate array."
        )
    values = np.asarray(scales, dtype=np.float64)
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        raise ConfigurationError("Correlation scales must be positive and finite.")
    return values


def correlation_from_lags(
    lags: FloatArray,
    scales: tuple[float, ...],
    model: CorrelationKind,
) -> FloatArray:
    """Evaluate a correlation model for lag vectors in the final axis."""
    values = np.asarray(lags, dtype=np.float64)
    if values.ndim == 0:
        raise ConfigurationError("Lag input must have a coordinate axis.")
    scale_array = _validated_scales(scales, values.shape[-1])
    normalized = values / scale_array
    if model is CorrelationKind.EXPONENTIAL:
        exponent = -2.0 * np.sum(np.abs(normalized), axis=-1)
    elif model is CorrelationKind.SQUARED_EXPONENTIAL:
        exponent = -math.pi * np.sum(normalized * normalized, axis=-1)
    else:  # pragma: no cover - protected by the enum type
        raise ConfigurationError(f"Unsupported correlation model: {model!r}")
    return np.asarray(np.exp(exponent), dtype=np.float64)


def pairwise_correlation(
    points: FloatArray,
    scales: tuple[float, ...],
    model: CorrelationKind,
) -> FloatArray:
    """Construct a dense unit-variance correlation matrix."""
    coordinates = np.asarray(points, dtype=np.float64)
    if coordinates.ndim != 2 or coordinates.shape[0] < 1:
        raise ConfigurationError("Points must have shape (n_points, dimension).")
    if not np.all(np.isfinite(coordinates)):
        raise ConfigurationError("Point coordinates must be finite.")
    scale_array = _validated_scales(scales, coordinates.shape[1])
    normalized = coordinates / scale_array
    if model is CorrelationKind.EXPONENTIAL:
        distance = cdist(normalized, normalized, metric="cityblock")
        matrix = np.exp(-2.0 * distance)
    elif model is CorrelationKind.SQUARED_EXPONENTIAL:
        distance_squared = cdist(normalized, normalized, metric="sqeuclidean")
        matrix = np.exp(-math.pi * distance_squared)
    else:  # pragma: no cover
        raise ConfigurationError(f"Unsupported correlation model: {model!r}")
    np.fill_diagonal(matrix, 1.0)
    return np.asarray(matrix, dtype=np.float64)


def exponential_cell_average_variance_factor(
    cell_size: float | FloatArray,
    scale: float | FloatArray,
) -> FloatArray:
    """Return the variance ratio for one-dimensional interval averaging.

    For ``rho(h) = exp(-2 |h| / theta)`` and ``r = D/theta``,

    ``v(r) = [exp(-2r) + 2r - 1] / (2r^2)``.

    A series expansion avoids cancellation for very small ``r``.
    """
    size = np.asarray(cell_size, dtype=np.float64)
    theta = np.asarray(scale, dtype=np.float64)
    if np.any(~np.isfinite(size)) or np.any(~np.isfinite(theta)):
        raise ConfigurationError("Cell dimensions and scales must be finite.")
    if np.any(size <= 0.0) or np.any(theta <= 0.0):
        raise ConfigurationError("Cell dimensions and scales must be positive.")
    r = size / theta
    small = r < 1.0e-4
    direct = (np.expm1(-2.0 * r) + 2.0 * r) / (2.0 * r * r)
    series = 1.0 - (2.0 / 3.0) * r + (1.0 / 3.0) * r**2 - (2.0 / 15.0) * r**3
    return np.asarray(np.where(small, series, direct), dtype=np.float64)


def exponential_cell_average_covariance_1d(
    center_separation: float | FloatArray,
    cell_size: float,
    scale: float,
) -> FloatArray:
    """Return covariance of equal interval averages for nonoverlapping cells.

    The point field has unit variance. Separations must be zero or at least one
    cell width. This covers the integer cell lags used by structured-grid
    validation.
    """
    separation = np.asarray(center_separation, dtype=np.float64)
    if cell_size <= 0.0 or scale <= 0.0:
        raise ConfigurationError("Cell size and scale must be positive.")
    if np.any(separation < 0.0):
        raise ConfigurationError("Center separation cannot be negative.")
    invalid = (separation > 0.0) & (separation < cell_size)
    if np.any(invalid):
        raise ConfigurationError("Overlapping unequal-lag interval averages are not supported.")

    zero = separation == 0.0
    q = 2.0 * cell_size / scale
    nonoverlap = np.exp((-2.0 / scale) * (separation - cell_size)) * (-np.expm1(-q)) ** 2 / (q * q)
    variance = exponential_cell_average_variance_factor(cell_size, scale)
    return np.asarray(np.where(zero, variance, nonoverlap), dtype=np.float64)
