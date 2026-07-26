"""Dense covariance/Karhunen-Loeve simulation at irregular coordinates."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import eigh

from rfieldmesh.config.models import CorrelationConfig, KLConfig
from rfieldmesh.exceptions import (
    ComputationalBudgetError,
    ConfigurationError,
    NumericalStabilityError,
)
from rfieldmesh.random_fields.correlations import pairwise_correlation
from rfieldmesh.random_fields.observations import GaussianFieldRealization

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class KLDiagnostics:
    """Numerical diagnostics for a covariance/KL preparation."""

    point_count: int
    retained_modes: int
    retained_variance_fraction: float
    truncation_error: float
    minimum_raw_eigenvalue: float
    normalized_point_variance: bool
    covariance_memory_bytes: int


@dataclass(frozen=True, slots=True)
class PreparedCovarianceKL:
    """Reusable low-rank factor of a Gaussian correlation matrix."""

    points: FloatArray
    factor: FloatArray
    latent_variance: FloatArray
    diagnostics: KLDiagnostics

    @classmethod
    def prepare(
        cls,
        points: FloatArray,
        correlation: CorrelationConfig,
        *,
        config: KLConfig | None = None,
    ) -> PreparedCovarianceKL:
        """Build, validate, and truncate a dense covariance decomposition."""
        options = KLConfig() if config is None else config
        coordinates = np.asarray(points, dtype=np.float64)
        if coordinates.ndim != 2 or coordinates.shape[0] < 2:
            raise ConfigurationError("KL coordinates must have shape (n_points, dimension).")
        if coordinates.shape[0] > options.max_points:
            raise ComputationalBudgetError(
                f"KL preparation received {coordinates.shape[0]:,} points, exceeding "
                f"max_points={options.max_points:,}."
            )
        if coordinates.shape[1] != len(correlation.scales):
            raise ConfigurationError("Coordinate dimension and correlation scales do not match.")

        covariance = pairwise_correlation(
            coordinates,
            correlation.scales,
            correlation.model,
        )
        covariance = 0.5 * (covariance + covariance.T)
        eigenvalues, eigenvectors = eigh(covariance, check_finite=True)
        minimum_raw = float(eigenvalues[0])
        largest = float(eigenvalues[-1])
        negative_tolerance = options.eigenvalue_tolerance * max(largest, 1.0)
        if minimum_raw < -negative_tolerance:
            raise NumericalStabilityError(
                f"The covariance matrix has a materially negative eigenvalue: {minimum_raw:.6e}."
            )
        eigenvalues = np.where(eigenvalues < 0.0, 0.0, eigenvalues)
        order = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[order]
        eigenvectors = eigenvectors[:, order]
        total_variance = float(np.sum(eigenvalues))
        if total_variance <= 0.0:
            raise NumericalStabilityError("The covariance matrix has no positive variance.")

        if options.retained_variance >= 1.0 - 1.0e-15:
            retained_modes = int(np.count_nonzero(eigenvalues > negative_tolerance))
        else:
            cumulative = np.cumsum(eigenvalues) / total_variance
            retained_modes = int(np.searchsorted(cumulative, options.retained_variance) + 1)
        retained_modes = max(1, retained_modes)
        retained_values = eigenvalues[:retained_modes]
        retained_vectors = eigenvectors[:, :retained_modes]
        factor = retained_vectors * np.sqrt(retained_values)
        raw_point_variance = np.sum(factor * factor, axis=1)
        if np.any(raw_point_variance <= 0.0):
            raise NumericalStabilityError("KL truncation produced a zero-variance point.")

        if options.normalize_point_variance:
            factor = factor / np.sqrt(raw_point_variance)[:, None]
            point_variance = np.ones(coordinates.shape[0], dtype=np.float64)
        else:
            point_variance = np.asarray(raw_point_variance, dtype=np.float64)

        retained_fraction = float(np.sum(retained_values) / total_variance)
        diagnostics = KLDiagnostics(
            point_count=int(coordinates.shape[0]),
            retained_modes=retained_modes,
            retained_variance_fraction=retained_fraction,
            truncation_error=1.0 - retained_fraction,
            minimum_raw_eigenvalue=minimum_raw,
            normalized_point_variance=options.normalize_point_variance,
            covariance_memory_bytes=int(covariance.nbytes),
        )
        return cls(
            points=np.array(coordinates, copy=True),
            factor=np.asarray(factor, dtype=np.float64),
            latent_variance=point_variance,
            diagnostics=diagnostics,
        )

    def generate(self, rng: np.random.Generator) -> GaussianFieldRealization:
        """Generate one latent realization from the cached low-rank factor."""
        independent = rng.standard_normal(self.factor.shape[1])
        values = self.factor @ independent
        return GaussianFieldRealization(
            values=np.asarray(values, dtype=np.float64),
            latent_variance=np.asarray(self.latent_variance, dtype=np.float64),
            diagnostics=self.diagnostics,
        )

    def reconstructed_correlation(self) -> FloatArray:
        """Return the covariance/correlation implied by the retained factor."""
        return np.asarray(self.factor @ self.factor.T, dtype=np.float64)
