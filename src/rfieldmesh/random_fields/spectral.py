"""Corrected finite Fourier-series simulation for a 2D exponential field."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from rfieldmesh.config.enums import MappingMethod
from rfieldmesh.config.models import SpectralConfig
from rfieldmesh.exceptions import ComputationalBudgetError, ConfigurationError
from rfieldmesh.random_fields.correlations import (
    exponential_cell_average_variance_factor,
)
from rfieldmesh.random_fields.observations import (
    GaussianFieldRealization,
    StructuredGrid2D,
)

FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]
IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class SpectralDiagnostics:
    """Preparation diagnostics recorded for every realization."""

    periods: tuple[float, float]
    mode_counts: tuple[int, int]
    directional_retained_variance: tuple[float, float]
    minimum_directional_observation_retained_fraction: tuple[float, float]
    retained_point_variance: float
    coefficient_count: int
    selection_method: str


def _unit_exponential_coefficients(
    period: float,
    scale: float,
    indices: IntArray,
) -> FloatArray:
    """Fourier coefficients of the periodicized unit exponential covariance."""
    kappa = 2.0 / scale
    omega = 2.0 * math.pi * indices / period
    parity = np.where(indices % 2 == 0, 1.0, -1.0)
    coefficients = (
        (2.0 / period)
        * kappa
        * (1.0 - math.exp(-kappa * period / 2.0) * parity)
        / (kappa * kappa + omega * omega)
    )
    if np.any(coefficients <= 0.0) or np.any(~np.isfinite(coefficients)):
        raise ConfigurationError("The exponential Fourier coefficients are not positive finite.")
    return np.asarray(coefficients, dtype=np.float64)


def _select_directional_modes(
    period: float,
    scale: float,
    config: SpectralConfig,
    mapping: MappingMethod,
    minimum_cell_width: float,
) -> tuple[IntArray, FloatArray, str]:
    if config.legacy_relative_threshold is not None:
        cap = min(10_000, config.max_mode_cap)
        indices = np.arange(-cap, cap + 1, dtype=np.int64)
        coefficients = _unit_exponential_coefficients(period, scale, indices)
        keep = coefficients > config.legacy_relative_threshold
        return indices[keep], coefficients[keep], "legacy_relative_coefficient"

    cap = 8
    while True:
        indices = np.arange(-cap, cap + 1, dtype=np.int64)
        coefficients = _unit_exponential_coefficients(period, scale, indices)
        if mapping is MappingMethod.RECTANGULAR_GAUSSIAN_AVERAGE:
            omega = 2.0 * math.pi * indices / period
            filter_squared = np.sinc(omega * minimum_cell_width / (2.0 * math.pi)) ** 2
            retained_observation_variance = float(np.sum(coefficients * filter_squared))
            target_observation_variance = float(
                exponential_cell_average_variance_factor(
                    minimum_cell_width,
                    scale,
                )
            )
            retained_fraction = retained_observation_variance / target_observation_variance
            selection_method = "retained_observation_variance"
        else:
            retained_fraction = float(np.sum(coefficients))
            selection_method = "retained_point_variance"
        if retained_fraction >= config.retained_variance:
            return indices, coefficients, selection_method
        if cap >= config.max_mode_cap:
            raise ComputationalBudgetError(
                "The requested retained spectral variance was not reached before max_mode_cap."
            )
        cap = min(config.max_mode_cap, cap * 2)


def _basis(
    centers: FloatArray,
    widths: FloatArray,
    indices: IntArray,
    period: float,
    mapping: MappingMethod,
) -> ComplexArray:
    omega = 2.0 * math.pi * indices / period
    phase = np.outer(centers, omega)
    basis = np.exp(1j * phase)
    if mapping is MappingMethod.RECTANGULAR_GAUSSIAN_AVERAGE:
        arguments = np.outer(widths, omega) / (2.0 * math.pi)
        basis = basis * np.sinc(arguments)
    elif mapping is not MappingMethod.CENTROID_SAMPLE:
        raise ConfigurationError(f"Unsupported spectral mapping method: {mapping!r}")
    return np.asarray(basis, dtype=np.complex128)


@dataclass(frozen=True, slots=True)
class PreparedSpectralExponential2D:
    """Reusable prepared representation of a standard Gaussian field."""

    grid: StructuredGrid2D
    scales: tuple[float, float]
    mapping: MappingMethod
    x_indices: IntArray
    z_indices: IntArray
    x_coefficients: FloatArray
    z_coefficients: FloatArray
    x_basis: ComplexArray
    z_basis: ComplexArray
    diagnostics: SpectralDiagnostics

    @classmethod
    def prepare(
        cls,
        grid: StructuredGrid2D,
        scales: tuple[float, float],
        *,
        mapping: MappingMethod = MappingMethod.RECTANGULAR_GAUSSIAN_AVERAGE,
        config: SpectralConfig | None = None,
    ) -> PreparedSpectralExponential2D:
        """Prepare Fourier coefficients and the observation basis."""
        options = SpectralConfig() if config is None else config
        if len(scales) != 2 or any(not math.isfinite(v) or v <= 0.0 for v in scales):
            raise ConfigurationError("Two positive finite scales are required.")
        extent_x, extent_z = grid.extent
        period_x = extent_x + options.padding_scale * scales[0]
        period_z = extent_z + options.padding_scale * scales[1]
        x_indices, x_coefficients, selection_x = _select_directional_modes(
            period_x,
            scales[0],
            options,
            mapping,
            float(np.min(grid.x_widths)),
        )
        z_indices, z_coefficients, selection_z = _select_directional_modes(
            period_z,
            scales[1],
            options,
            mapping,
            float(np.min(grid.z_widths)),
        )
        coefficient_count = int(x_indices.size * z_indices.size)
        if coefficient_count > options.max_coefficient_count:
            raise ComputationalBudgetError(
                f"The spectral coefficient matrix requires {coefficient_count:,} entries, "
                f"exceeding the configured limit of {options.max_coefficient_count:,}."
            )
        x_basis = _basis(
            grid.x_centers,
            grid.x_widths,
            x_indices,
            period_x,
            mapping,
        )
        z_basis = _basis(
            grid.z_centers,
            grid.z_widths,
            z_indices,
            period_z,
            mapping,
        )
        retained_x = float(np.sum(x_coefficients))
        retained_z = float(np.sum(z_coefficients))
        observed_x = np.abs(x_basis) ** 2 @ x_coefficients
        observed_z = np.abs(z_basis) ** 2 @ z_coefficients
        if mapping is MappingMethod.RECTANGULAR_GAUSSIAN_AVERAGE:
            target_x = exponential_cell_average_variance_factor(
                grid.x_widths,
                scales[0],
            )
            target_z = exponential_cell_average_variance_factor(
                grid.z_widths,
                scales[1],
            )
            minimum_observed_fraction = (
                float(np.min(observed_x / target_x)),
                float(np.min(observed_z / target_z)),
            )
        else:
            minimum_observed_fraction = (retained_x, retained_z)
        diagnostics = SpectralDiagnostics(
            periods=(period_x, period_z),
            mode_counts=(int(x_indices.size), int(z_indices.size)),
            directional_retained_variance=(retained_x, retained_z),
            minimum_directional_observation_retained_fraction=(minimum_observed_fraction),
            retained_point_variance=retained_x * retained_z,
            coefficient_count=coefficient_count,
            selection_method=(
                selection_x if selection_x == selection_z else f"{selection_x}+{selection_z}"
            ),
        )
        return cls(
            grid=grid,
            scales=scales,
            mapping=mapping,
            x_indices=x_indices,
            z_indices=z_indices,
            x_coefficients=x_coefficients,
            z_coefficients=z_coefficients,
            x_basis=x_basis,
            z_basis=z_basis,
            diagnostics=diagnostics,
        )

    def generate(self, rng: np.random.Generator) -> GaussianFieldRealization:
        """Generate one zero-mean latent Gaussian realization."""
        covariance_coefficients = np.outer(self.x_coefficients, self.z_coefficients)
        coefficient_scale = np.sqrt(covariance_coefficients)
        random_coefficients = coefficient_scale * (
            rng.standard_normal(covariance_coefficients.shape)
            + 1j * rng.standard_normal(covariance_coefficients.shape)
        )
        values = np.real(self.x_basis @ random_coefficients @ self.z_basis.T)
        x_variance = np.abs(self.x_basis) ** 2 @ self.x_coefficients
        z_variance = np.abs(self.z_basis) ** 2 @ self.z_coefficients
        latent_variance = np.outer(x_variance, z_variance)
        return GaussianFieldRealization(
            values=np.asarray(values, dtype=np.float64),
            latent_variance=np.asarray(latent_variance, dtype=np.float64),
            diagnostics=self.diagnostics,
        )
