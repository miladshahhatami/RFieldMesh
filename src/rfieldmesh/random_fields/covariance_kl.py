"""Dense KL or scalable pivoted-covariance simulation at general coordinates."""

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
from rfieldmesh.random_fields.correlations import correlation_from_lags, pairwise_correlation
from rfieldmesh.random_fields.observations import GaussianFieldRealization

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class KLDiagnostics:
    """Numerical diagnostics for a covariance/KL preparation."""

    point_count: int
    retained_modes: int
    retained_variance_fraction: float
    truncation_error: float
    minimum_raw_eigenvalue: float | None
    normalized_point_variance: bool
    covariance_memory_bytes: int
    estimated_dense_memory_bytes: int
    working_memory_bytes: int
    factorization: str


@dataclass(frozen=True, slots=True)
class PreparedCovarianceKL:
    """Reusable low-rank factor of a Gaussian correlation matrix."""

    points: FloatArray
    factor: FloatArray
    latent_variance: FloatArray
    diagnostics: KLDiagnostics

    @staticmethod
    def _correlation_column(
        coordinates: FloatArray,
        pivot: int,
        correlation: CorrelationConfig,
        block_size: int,
    ) -> FloatArray:
        """Evaluate one covariance column without allocating an N-by-N matrix."""
        result = np.empty(coordinates.shape[0], dtype=np.float64)
        for start in range(0, coordinates.shape[0], block_size):
            stop = min(start + block_size, coordinates.shape[0])
            result[start:stop] = correlation_from_lags(
                coordinates[start:stop] - coordinates[pivot],
                correlation.scales,
                correlation.model,
            )
        result[pivot] = 1.0
        return result

    @classmethod
    def _pivoted_factor(
        cls,
        coordinates: FloatArray,
        correlation: CorrelationConfig,
        options: KLConfig,
    ) -> tuple[FloatArray, float, int]:
        """Construct a matrix-free pivoted-Cholesky covariance factor.

        The stopping rule uses the unresolved covariance trace, so the retained
        fraction has the same total-variance interpretation as KL truncation.
        """
        point_count = coordinates.shape[0]
        max_modes = min(options.iterative_max_modes, point_count)
        estimated_working = (
            point_count * max_modes * np.dtype(np.float64).itemsize
            + 3 * point_count * np.dtype(np.float64).itemsize
        )
        if estimated_working > options.iterative_memory_limit_mb * 1024**2:
            raise ComputationalBudgetError(
                "The scalable covariance factor would require approximately "
                f"{estimated_working / 1024**2:.1f} MiB, exceeding "
                f"iterative_memory_limit_mb={options.iterative_memory_limit_mb:g}."
            )
        factor = np.empty((point_count, max_modes), dtype=np.float64)
        residual = np.ones(point_count, dtype=np.float64)
        initial_trace = float(point_count)
        retained_fraction = 0.0
        retained_modes = 0
        absolute_tolerance = options.eigenvalue_tolerance
        for mode in range(max_modes):
            pivot = int(np.argmax(residual))
            pivot_residual = float(residual[pivot])
            if pivot_residual <= absolute_tolerance:
                break
            column = cls._correlation_column(
                coordinates,
                pivot,
                correlation,
                options.block_size,
            )
            if mode:
                column -= factor[:, :mode] @ factor[pivot, :mode]
            new_mode = column / np.sqrt(pivot_residual)
            factor[:, mode] = new_mode
            residual = np.maximum(residual - new_mode * new_mode, 0.0)
            retained_modes = mode + 1
            retained_fraction = 1.0 - float(np.sum(residual)) / initial_trace
            if retained_fraction + 1.0e-12 >= options.retained_variance:
                break
        if retained_modes == 0:
            raise NumericalStabilityError("Scalable covariance factorization retained no mode.")
        if retained_fraction + 1.0e-12 < options.retained_variance:
            working = point_count * retained_modes * np.dtype(np.float64).itemsize
            raise ComputationalBudgetError(
                "The scalable covariance factor reached iterative_max_modes="
                f"{options.iterative_max_modes:,} after retaining "
                f"{retained_fraction:.6f} of the covariance trace; the requested fraction is "
                f"{options.retained_variance:.6f}. Estimated factor memory is "
                f"{working / 1024**2:.1f} MiB. Increase the mode or memory budget, use larger "
                "correlation scales, or use a structured spectral configuration."
            )
        return (
            np.asarray(factor[:, :retained_modes], dtype=np.float64),
            retained_fraction,
            estimated_working,
        )

    @classmethod
    def prepare(
        cls,
        points: FloatArray,
        correlation: CorrelationConfig,
        *,
        config: KLConfig | None = None,
    ) -> PreparedCovarianceKL:
        """Build a dense KL or matrix-free low-rank covariance factor."""
        options = KLConfig() if config is None else config
        coordinates = np.asarray(points, dtype=np.float64)
        if coordinates.ndim != 2 or coordinates.shape[0] < 2:
            raise ConfigurationError("KL coordinates must have shape (n_points, dimension).")
        if coordinates.shape[1] != len(correlation.scales):
            raise ConfigurationError("Coordinate dimension and correlation scales do not match.")
        if not np.all(np.isfinite(coordinates)):
            raise ConfigurationError("KL coordinates must be finite.")

        point_count = coordinates.shape[0]
        covariance_bytes = point_count * point_count * np.dtype(np.float64).itemsize
        estimated_dense = 3 * covariance_bytes
        dense_allowed = estimated_dense <= options.dense_memory_limit_mb * 1024**2
        minimum_raw: float | None
        if dense_allowed:
            covariance = pairwise_correlation(
                coordinates,
                correlation.scales,
                correlation.model,
            )
            covariance = 0.5 * (covariance + covariance.T)
            eigenvalues, eigenvectors = eigh(covariance, check_finite=True)
            minimum_raw_value = float(eigenvalues[0])
            largest = float(eigenvalues[-1])
            negative_tolerance = options.eigenvalue_tolerance * max(largest, 1.0)
            if minimum_raw_value < -negative_tolerance:
                raise NumericalStabilityError(
                    "The covariance matrix has a materially negative eigenvalue: "
                    f"{minimum_raw_value:.6e}."
                )
            minimum_raw = minimum_raw_value
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
            retained_fraction = float(np.sum(retained_values) / total_variance)
            factorization = "dense_kl"
            working_memory = estimated_dense
            covariance_memory = int(covariance.nbytes)
        else:
            factor, retained_fraction, working_memory = cls._pivoted_factor(
                coordinates,
                correlation,
                options,
            )
            retained_modes = factor.shape[1]
            minimum_raw = None
            factorization = "pivoted_cholesky"
            covariance_memory = 0
        raw_point_variance = np.sum(factor * factor, axis=1)
        if np.any(raw_point_variance <= 0.0):
            raise NumericalStabilityError("KL truncation produced a zero-variance point.")

        if options.normalize_point_variance:
            factor = factor / np.sqrt(raw_point_variance)[:, None]
            point_variance = np.ones(coordinates.shape[0], dtype=np.float64)
        else:
            point_variance = np.asarray(raw_point_variance, dtype=np.float64)

        diagnostics = KLDiagnostics(
            point_count=int(coordinates.shape[0]),
            retained_modes=retained_modes,
            retained_variance_fraction=retained_fraction,
            truncation_error=1.0 - retained_fraction,
            minimum_raw_eigenvalue=minimum_raw,
            normalized_point_variance=options.normalize_point_variance,
            covariance_memory_bytes=covariance_memory,
            estimated_dense_memory_bytes=estimated_dense,
            working_memory_bytes=int(working_memory),
            factorization=factorization,
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
