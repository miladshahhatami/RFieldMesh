"""Deterministic statistical summaries for generated fields."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from rfieldmesh.exceptions import ConfigurationError

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class FieldStatistics:
    """Physical-space sample summary using population standard deviation."""

    count: int
    minimum: float
    maximum: float
    sample_mean: float
    sample_standard_deviation: float
    sample_coefficient_of_variation: float
    target_mean: float
    target_standard_deviation: float
    mean_bias: float
    relative_mean_bias: float
    standard_deviation_bias: float
    relative_standard_deviation_bias: float
    nonfinite_count: int

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping."""
        return asdict(self)


def field_statistics(
    values: FloatArray,
    *,
    target_mean: float,
    target_standard_deviation: float,
) -> FieldStatistics:
    """Calculate a complete target-versus-sample summary."""
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        raise ConfigurationError("Cannot summarize an empty field.")
    finite = np.isfinite(array)
    nonfinite_count = int(array.size - np.count_nonzero(finite))
    if nonfinite_count:
        raise ConfigurationError(f"The field contains {nonfinite_count} nonfinite values.")
    if not math.isfinite(target_mean) or not math.isfinite(target_standard_deviation):
        raise ConfigurationError("Target moments must be finite.")
    if target_mean == 0.0 or target_standard_deviation <= 0.0:
        raise ConfigurationError(
            "Target mean must be nonzero and target standard deviation positive."
        )

    sample_mean = float(np.mean(array))
    sample_std = float(np.std(array, ddof=0))
    mean_bias = sample_mean - target_mean
    std_bias = sample_std - target_standard_deviation
    return FieldStatistics(
        count=int(array.size),
        minimum=float(np.min(array)),
        maximum=float(np.max(array)),
        sample_mean=sample_mean,
        sample_standard_deviation=sample_std,
        sample_coefficient_of_variation=sample_std / sample_mean,
        target_mean=target_mean,
        target_standard_deviation=target_standard_deviation,
        mean_bias=mean_bias,
        relative_mean_bias=mean_bias / target_mean,
        standard_deviation_bias=std_bias,
        relative_standard_deviation_bias=std_bias / target_standard_deviation,
        nonfinite_count=0,
    )


def empirical_axis_correlation(
    values: FloatArray,
    *,
    axis: int,
    maximum_lag: int,
) -> FloatArray:
    """Estimate normalized spatial correlation for integer grid lags."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or axis not in (0, 1):
        raise ConfigurationError("A two-dimensional field and axis 0 or 1 are required.")
    if maximum_lag < 0 or maximum_lag >= array.shape[axis]:
        raise ConfigurationError("maximum_lag must be smaller than the selected axis length.")
    centered = array - np.mean(array)
    variance = float(np.mean(centered * centered))
    if variance <= 0.0:
        raise ConfigurationError("Empirical correlation requires nonzero field variance.")
    correlations = np.empty(maximum_lag + 1, dtype=np.float64)
    correlations[0] = 1.0
    for lag in range(1, maximum_lag + 1):
        left = [slice(None), slice(None)]
        right = [slice(None), slice(None)]
        left[axis] = slice(0, -lag)
        right[axis] = slice(lag, None)
        correlations[lag] = float(
            np.mean(centered[tuple(left)] * centered[tuple(right)]) / variance
        )
    return correlations
