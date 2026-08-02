"""Covariance/Karhunen-Loeve tests."""

import numpy as np

from rfieldmesh.config.enums import CorrelationKind, PropertyKind
from rfieldmesh.config.models import CorrelationConfig, KLConfig
from rfieldmesh.random_fields.correlations import pairwise_correlation
from rfieldmesh.random_fields.covariance_kl import PreparedCovarianceKL
from rfieldmesh.random_fields.rng import rng_for_realization


def test_full_kl_reconstructs_correlation_matrix() -> None:
    points = np.array(
        [[0.0, 0.0], [0.5, 0.0], [1.5, 0.4], [2.0, 1.0]],
        dtype=np.float64,
    )
    correlation = CorrelationConfig(
        model=CorrelationKind.EXPONENTIAL,
        scales=(2.0, 1.0),
    )
    prepared = PreparedCovarianceKL.prepare(
        points,
        correlation,
        config=KLConfig(retained_variance=1.0, normalize_point_variance=False),
    )
    expected = pairwise_correlation(points, correlation.scales, correlation.model)
    assert np.allclose(prepared.reconstructed_correlation(), expected, atol=1.0e-12)
    assert prepared.diagnostics.truncation_error < 1.0e-14


def test_truncated_kl_normalizes_point_variance() -> None:
    points = np.column_stack((np.linspace(0.0, 5.0, 20), np.zeros(20)))
    prepared = PreparedCovarianceKL.prepare(
        points,
        CorrelationConfig(scales=(2.0, 1.0)),
        config=KLConfig(retained_variance=0.95, normalize_point_variance=True),
    )
    assert prepared.diagnostics.retained_modes < points.shape[0]
    assert np.allclose(np.diag(prepared.reconstructed_correlation()), 1.0)


def test_kl_generation_is_reproducible() -> None:
    points = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    prepared = PreparedCovarianceKL.prepare(
        points,
        CorrelationConfig(scales=(1.0, 1.0)),
    )
    first = prepared.generate(rng_for_realization(4, 0, PropertyKind.DENSITY))
    second = prepared.generate(rng_for_realization(4, 0, PropertyKind.DENSITY))
    assert np.array_equal(first.values, second.values)


def test_large_general_mesh_uses_matrix_free_factorization() -> None:
    points = np.column_stack((np.linspace(0.0, 10.0, 300), np.zeros(300)))
    prepared = PreparedCovarianceKL.prepare(
        points,
        CorrelationConfig(scales=(100.0, 100.0)),
        config=KLConfig(
            retained_variance=0.95,
            dense_memory_limit_mb=1.1,
            iterative_max_modes=32,
            max_points=2,  # legacy field is accepted but no longer rejects by point count
        ),
    )
    assert prepared.diagnostics.factorization == "pivoted_cholesky"
    assert prepared.diagnostics.covariance_memory_bytes == 0
    assert prepared.diagnostics.retained_variance_fraction >= 0.95
