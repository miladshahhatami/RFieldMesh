"""Statistical summary tests."""

import numpy as np
import pytest

from rfieldmesh.random_fields.statistics import (
    empirical_axis_correlation,
    field_statistics,
)


def test_field_statistics_use_population_standard_deviation() -> None:
    values = np.array([1.0, 2.0, 3.0])
    result = field_statistics(
        values,
        target_mean=2.0,
        target_standard_deviation=1.0,
    )
    assert result.sample_mean == 2.0
    assert result.sample_standard_deviation == pytest.approx(np.sqrt(2.0 / 3.0))
    assert result.count == 3


def test_empirical_axis_correlation_at_zero_is_one() -> None:
    values = np.arange(20.0).reshape(5, 4)
    result = empirical_axis_correlation(values, axis=0, maximum_lag=2)
    assert result[0] == 1.0
    assert result.shape == (3,)
