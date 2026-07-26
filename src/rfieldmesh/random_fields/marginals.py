"""Physical-space marginal transformations."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares
from scipy.stats import norm, truncnorm

from rfieldmesh.config.enums import DistributionKind
from rfieldmesh.config.models import BoundsConfig, MomentSpecification
from rfieldmesh.exceptions import ConfigurationError, UnsupportedObservationError

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class LognormalParameters:
    """Latent Gaussian parameters for a physical lognormal variable."""

    mean_log: float
    standard_deviation_log: float


@dataclass(frozen=True, slots=True)
class TruncatedNormalParameters:
    """Underlying normal parameters and standardized truncation limits."""

    location: float
    scale: float
    standardized_lower: float
    standardized_upper: float


def lognormal_latent_parameters(mean: float, standard_deviation: float) -> LognormalParameters:
    """Convert physical lognormal moments to latent Gaussian parameters."""
    if not math.isfinite(mean) or not math.isfinite(standard_deviation):
        raise ConfigurationError("Lognormal moments must be finite.")
    if mean <= 0.0 or standard_deviation <= 0.0:
        raise ConfigurationError("Lognormal mean and standard deviation must be positive.")
    covariance = standard_deviation / mean
    variance_log = math.log1p(covariance * covariance)
    return LognormalParameters(
        mean_log=math.log(mean) - 0.5 * variance_log,
        standard_deviation_log=math.sqrt(variance_log),
    )


def lognormal_physical_correlation(
    latent_correlation: FloatArray,
    standard_deviation_log: float,
) -> FloatArray:
    """Map equal-marginal latent Gaussian correlation to physical correlation."""
    rho = np.asarray(latent_correlation, dtype=np.float64)
    variance_log = standard_deviation_log * standard_deviation_log
    denominator = math.expm1(variance_log)
    return np.asarray(np.expm1(variance_log * rho) / denominator, dtype=np.float64)


def fit_truncated_normal(
    moments: MomentSpecification,
    bounds: BoundsConfig,
) -> TruncatedNormalParameters:
    """Fit underlying normal parameters to bounded physical moments."""
    mean = moments.mean
    target_std = moments.standard_deviation
    lower = -math.inf if bounds.lower is None else bounds.lower
    upper = math.inf if bounds.upper is None else bounds.upper

    if not lower < mean < upper:
        raise ConfigurationError("The truncated-normal mean must lie strictly within its bounds.")
    if math.isfinite(lower) and math.isfinite(upper):
        maximum_variance = (mean - lower) * (upper - mean)
        if target_std * target_std >= maximum_variance:
            raise ConfigurationError(
                "The requested variance is incompatible with the finite bounds and mean."
            )

    def distribution_stats(location: float, scale: float) -> tuple[float, float]:
        a = (lower - location) / scale
        b = (upper - location) / scale
        fitted_mean, fitted_variance = truncnorm.stats(
            a,
            b,
            loc=location,
            scale=scale,
            moments="mv",
        )
        return float(fitted_mean), math.sqrt(float(fitted_variance))

    def residual(parameters: FloatArray) -> FloatArray:
        location = float(parameters[0])
        scale = math.exp(float(parameters[1]))
        try:
            fitted_mean, fitted_std = distribution_stats(location, scale)
        except (FloatingPointError, ValueError):
            return np.array([1.0e6, 1.0e6], dtype=np.float64)
        if not math.isfinite(fitted_mean) or not math.isfinite(fitted_std):
            return np.array([1.0e6, 1.0e6], dtype=np.float64)
        return np.array(
            [
                (fitted_mean - mean) / target_std,
                (fitted_std - target_std) / target_std,
            ],
            dtype=np.float64,
        )

    result = least_squares(
        residual,
        x0=np.array([mean, math.log(target_std)], dtype=np.float64),
        max_nfev=2_000,
        xtol=1.0e-13,
        ftol=1.0e-13,
        gtol=1.0e-13,
    )
    location = float(result.x[0])
    scale = math.exp(float(result.x[1]))
    fitted_mean, fitted_std = distribution_stats(location, scale)
    relative_error = max(
        abs(fitted_mean - mean) / target_std,
        abs(fitted_std - target_std) / target_std,
    )
    if not result.success or relative_error > 1.0e-7:
        raise ConfigurationError(
            "Could not fit a truncated-normal distribution to the requested moments and bounds."
        )
    return TruncatedNormalParameters(
        location=location,
        scale=scale,
        standardized_lower=(lower - location) / scale,
        standardized_upper=(upper - location) / scale,
    )


def apply_marginal(
    latent_values: FloatArray,
    moments: MomentSpecification,
    distribution: DistributionKind,
    *,
    bounds: BoundsConfig | None = None,
    latent_variance: FloatArray | None = None,
    preserve_lognormal_mean_after_averaging: bool = True,
) -> FloatArray:
    """Transform a latent Gaussian field to physical space.

    ``latent_variance`` describes the observation-scale variance of each latent
    value. It is used to restore the physical mean of a lognormal surrogate
    after Gaussian local averaging. It does not restore the point-scale
    coefficient of variation.
    """
    latent = np.asarray(latent_values, dtype=np.float64)
    if not np.all(np.isfinite(latent)):
        raise ConfigurationError("Latent Gaussian values must be finite.")
    variance = (
        np.ones_like(latent)
        if latent_variance is None
        else np.broadcast_to(np.asarray(latent_variance, dtype=np.float64), latent.shape)
    )
    if np.any(~np.isfinite(variance)) or np.any(variance <= 0.0):
        raise ConfigurationError("Latent observation variances must be positive and finite.")

    if distribution is DistributionKind.NORMAL:
        return np.asarray(
            moments.mean + moments.standard_deviation * latent,
            dtype=np.float64,
        )

    if distribution is DistributionKind.LOGNORMAL:
        lognormal_parameters = lognormal_latent_parameters(
            moments.mean,
            moments.standard_deviation,
        )
        variance_log = lognormal_parameters.standard_deviation_log**2
        correction = (
            np.exp(0.5 * variance_log * (1.0 - variance))
            if preserve_lognormal_mean_after_averaging
            else 1.0
        )
        return np.asarray(
            np.exp(
                lognormal_parameters.mean_log + lognormal_parameters.standard_deviation_log * latent
            )
            * correction,
            dtype=np.float64,
        )

    if distribution is DistributionKind.TRUNCATED_NORMAL:
        if bounds is None:
            raise ConfigurationError("Truncated-normal transformation requires bounds.")
        if not np.allclose(variance, 1.0, rtol=1.0e-9, atol=1.0e-12):
            raise UnsupportedObservationError(
                "Latent-Gaussian local averaging with a truncated-normal copula is not "
                "implemented. Use centroid sampling or physical-space subcell averaging."
            )
        truncated_parameters = fit_truncated_normal(moments, bounds)
        probabilities = norm.cdf(latent)
        lower_probability = np.nextafter(0.0, 1.0)
        upper_probability = np.nextafter(1.0, 0.0)
        probabilities = np.clip(probabilities, lower_probability, upper_probability)
        return np.asarray(
            truncnorm.ppf(
                probabilities,
                truncated_parameters.standardized_lower,
                truncated_parameters.standardized_upper,
                loc=truncated_parameters.location,
                scale=truncated_parameters.scale,
            ),
            dtype=np.float64,
        )

    raise ConfigurationError(f"Unsupported distribution: {distribution!r}")
