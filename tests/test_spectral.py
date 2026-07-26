"""Fourier spectral-method tests."""

import numpy as np
import pytest

from rfieldmesh.config.enums import MappingMethod, PropertyKind
from rfieldmesh.config.models import SpectralConfig
from rfieldmesh.random_fields.correlations import (
    exponential_cell_average_variance_factor,
)
from rfieldmesh.random_fields.observations import StructuredGrid2D
from rfieldmesh.random_fields.rng import rng_for_realization
from rfieldmesh.random_fields.spectral import PreparedSpectralExponential2D


def make_grid() -> StructuredGrid2D:
    return StructuredGrid2D(
        x_nodes=np.linspace(0.0, 8.0, 17),
        z_nodes=np.linspace(0.0, 4.0, 17),
    )


def test_spectral_realization_is_deterministic() -> None:
    prepared = PreparedSpectralExponential2D.prepare(
        make_grid(),
        scales=(3.0, 1.0),
    )
    first = prepared.generate(rng_for_realization(17, 0, PropertyKind.YOUNGS_MODULUS))
    second = prepared.generate(rng_for_realization(17, 0, PropertyKind.YOUNGS_MODULUS))
    assert np.array_equal(first.values, second.values)
    assert np.array_equal(first.latent_variance, second.latent_variance)


def test_cell_variance_matches_analytical_factor() -> None:
    grid = make_grid()
    prepared = PreparedSpectralExponential2D.prepare(
        grid,
        scales=(3.0, 1.0),
        mapping=MappingMethod.RECTANGULAR_GAUSSIAN_AVERAGE,
        config=SpectralConfig(retained_variance=0.999999),
    )
    result = prepared.generate(rng_for_realization(5, 0, PropertyKind.YOUNGS_MODULUS))
    expected = float(
        exponential_cell_average_variance_factor(0.5, 3.0)
        * exponential_cell_average_variance_factor(0.25, 1.0)
    )
    assert np.ptp(result.latent_variance) < 1.0e-12
    assert result.latent_variance[0, 0] == pytest.approx(expected, rel=2.0e-5)


def test_centroid_variance_equals_retained_point_variance() -> None:
    prepared = PreparedSpectralExponential2D.prepare(
        make_grid(),
        scales=(3.0, 1.0),
        mapping=MappingMethod.CENTROID_SAMPLE,
        config=SpectralConfig(retained_variance=0.99),
    )
    result = prepared.generate(rng_for_realization(5, 0, PropertyKind.YOUNGS_MODULUS))
    assert np.allclose(
        result.latent_variance,
        prepared.diagnostics.retained_point_variance,
    )


@pytest.mark.statistical
def test_empirical_variance_matches_reported_variance() -> None:
    grid = StructuredGrid2D(np.linspace(0.0, 2.0, 5), np.linspace(0.0, 1.0, 4))
    prepared = PreparedSpectralExponential2D.prepare(
        grid,
        scales=(2.0, 0.8),
    )
    samples = np.empty(500)
    for index in range(samples.size):
        realization = prepared.generate(
            rng_for_realization(800, index, PropertyKind.YOUNGS_MODULUS)
        )
        samples[index] = realization.values[1, 1]
    expected = prepared.generate(
        rng_for_realization(1, 0, PropertyKind.YOUNGS_MODULUS)
    ).latent_variance[1, 1]
    assert np.var(samples) == pytest.approx(expected, rel=0.13)
