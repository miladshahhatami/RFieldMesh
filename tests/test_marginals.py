"""Marginal-distribution transformation tests."""

import numpy as np
import pytest
from scipy.stats import truncnorm

from rfieldmesh.config.enums import DistributionKind
from rfieldmesh.config.models import BoundsConfig, MomentSpecification
from rfieldmesh.exceptions import UnsupportedObservationError
from rfieldmesh.random_fields.marginals import (
    apply_marginal,
    fit_truncated_normal,
    lognormal_latent_parameters,
)


def test_lognormal_parameters_reproduce_physical_moments() -> None:
    mean = 20.0e6
    standard_deviation = 6.0e6
    parameters = lognormal_latent_parameters(mean, standard_deviation)
    recovered_mean = np.exp(parameters.mean_log + 0.5 * parameters.standard_deviation_log**2)
    recovered_variance = np.expm1(parameters.standard_deviation_log**2) * np.exp(
        2.0 * parameters.mean_log + parameters.standard_deviation_log**2
    )
    assert recovered_mean == pytest.approx(mean)
    assert np.sqrt(recovered_variance) == pytest.approx(standard_deviation)


def test_lognormal_average_correction_restores_analytical_mean() -> None:
    moments = MomentSpecification(mean=100.0, standard_deviation=30.0)
    latent_variance = np.array([0.72])
    parameters = lognormal_latent_parameters(100.0, 30.0)
    transformed_at_zero = apply_marginal(
        np.array([0.0]),
        moments,
        DistributionKind.LOGNORMAL,
        latent_variance=latent_variance,
    )[0]
    expected_log_median = np.exp(parameters.mean_log)
    correction = np.exp(0.5 * parameters.standard_deviation_log**2 * (1.0 - latent_variance[0]))
    assert transformed_at_zero == pytest.approx(expected_log_median * correction)


def test_truncated_normal_fit_reproduces_requested_moments() -> None:
    moments = MomentSpecification(mean=1800.0, standard_deviation=180.0)
    bounds = BoundsConfig(lower=1200.0, upper=2300.0)
    parameters = fit_truncated_normal(moments, bounds)
    fitted_mean, fitted_variance = truncnorm.stats(
        parameters.standardized_lower,
        parameters.standardized_upper,
        loc=parameters.location,
        scale=parameters.scale,
        moments="mv",
    )
    assert float(fitted_mean) == pytest.approx(moments.mean, rel=1.0e-9)
    assert np.sqrt(float(fitted_variance)) == pytest.approx(
        moments.standard_deviation,
        rel=1.0e-9,
    )


def test_truncated_normal_transform_respects_bounds() -> None:
    moments = MomentSpecification(mean=1800.0, standard_deviation=180.0)
    bounds = BoundsConfig(lower=1200.0, upper=2300.0)
    latent = np.linspace(-7.0, 7.0, 1000)
    physical = apply_marginal(
        latent,
        moments,
        DistributionKind.TRUNCATED_NORMAL,
        bounds=bounds,
    )
    assert np.all(physical > 1200.0)
    assert np.all(physical < 2300.0)


def test_truncated_normal_rejects_gaussian_local_average() -> None:
    with pytest.raises(UnsupportedObservationError):
        apply_marginal(
            np.zeros(3),
            MomentSpecification(mean=10.0, standard_deviation=2.0),
            DistributionKind.TRUNCATED_NORMAL,
            bounds=BoundsConfig(lower=0.0),
            latent_variance=np.full(3, 0.8),
        )
