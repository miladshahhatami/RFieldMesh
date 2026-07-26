"""Correlation-equation and local-average tests."""

import numpy as np
import pytest
from scipy.integrate import quad

from rfieldmesh.config.enums import CorrelationKind
from rfieldmesh.random_fields.correlations import (
    correlation_from_lags,
    exponential_cell_average_covariance_1d,
    exponential_cell_average_variance_factor,
    pairwise_correlation,
)


def test_exponential_scale_convention() -> None:
    lags = np.array([[0.0, 0.0], [5.0, 0.5]], dtype=np.float64)
    result = correlation_from_lags(lags, (10.0, 1.0), CorrelationKind.EXPONENTIAL)
    assert result[0] == pytest.approx(1.0)
    assert result[1] == pytest.approx(np.exp(-2.0))


def test_squared_exponential_scale_convention() -> None:
    integral, _ = quad(lambda h: np.exp(-np.pi * (h / 3.5) ** 2), -np.inf, np.inf)
    assert integral == pytest.approx(3.5, rel=1.0e-10)


def test_pairwise_matrix_is_symmetric_with_unit_diagonal() -> None:
    points = np.array([[0.0, 0.0], [1.0, 2.0], [2.0, 1.0]])
    matrix = pairwise_correlation(points, (4.0, 2.0), CorrelationKind.EXPONENTIAL)
    assert np.allclose(matrix, matrix.T)
    assert np.allclose(np.diag(matrix), 1.0)


@pytest.mark.parametrize("ratio", [1.0e-7, 0.05, 0.5, 4.0])
def test_local_average_variance_matches_quadrature(ratio: float) -> None:
    scale = 2.3
    cell_size = ratio * scale
    integral, _ = quad(
        lambda h: 2.0 * (cell_size - h) * np.exp(-2.0 * h / scale) / cell_size**2,
        0.0,
        cell_size,
    )
    result = float(exponential_cell_average_variance_factor(cell_size, scale))
    assert result == pytest.approx(integral, rel=2.0e-8, abs=2.0e-10)


def test_adjacent_cell_covariance_matches_double_quadrature() -> None:
    scale = 1.7
    cell_size = 0.4
    expected, _ = quad(
        lambda x: quad(
            lambda y: np.exp(-2.0 * abs(y - x) / scale) / cell_size**2,
            cell_size,
            2.0 * cell_size,
        )[0],
        0.0,
        cell_size,
    )
    result = float(exponential_cell_average_covariance_1d(cell_size, cell_size, scale))
    assert result == pytest.approx(expected, rel=1.0e-9)
