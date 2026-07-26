"""Generate the Phase 3 numerical validation summary and Plotly report."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

import numpy as np
from scipy.stats import lognorm

from rfieldmesh.config.enums import DistributionKind, MappingMethod, PropertyKind
from rfieldmesh.config.models import MomentSpecification, SpectralConfig
from rfieldmesh.random_fields.correlations import (
    exponential_cell_average_covariance_1d,
    exponential_cell_average_variance_factor,
)
from rfieldmesh.random_fields.marginals import (
    apply_marginal,
    lognormal_latent_parameters,
)
from rfieldmesh.random_fields.observations import StructuredGrid2D
from rfieldmesh.random_fields.rng import rng_for_realization
from rfieldmesh.random_fields.spectral import PreparedSpectralExponential2D
from rfieldmesh.random_fields.statistics import (
    empirical_axis_correlation,
    field_statistics,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    project_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--reference",
        type=Path,
        default=project_root / "validation/matlab/E_field_lognormal_seed1403.csv",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=project_root / "validation/output",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    output_directory: Path = arguments.output_directory
    output_directory.mkdir(parents=True, exist_ok=True)

    target = MomentSpecification(
        mean=20_000_000.0,
        standard_deviation=6_000_000.0,
        unit_label="Pa",
    )
    grid = StructuredGrid2D(
        x_nodes=np.arange(0.0, 100.0 + 0.25, 0.5),
        z_nodes=np.arange(0.0, 50.0 + 0.25, 0.5),
    )
    reference = np.loadtxt(arguments.reference, delimiter=",")
    if reference.shape != grid.shape:
        raise ValueError(f"Expected reference shape {grid.shape}, received {reference.shape}.")

    prepared = PreparedSpectralExponential2D.prepare(
        grid,
        scales=(10.0, 1.0),
        mapping=MappingMethod.RECTANGULAR_GAUSSIAN_AVERAGE,
        config=SpectralConfig(
            legacy_relative_threshold=1.0e-5,
            max_coefficient_count=5_000_000,
        ),
    )
    rng = rng_for_realization(1403, 0, PropertyKind.YOUNGS_MODULUS)
    gaussian = prepared.generate(rng)
    generated = apply_marginal(
        gaussian.values,
        target,
        DistributionKind.LOGNORMAL,
        latent_variance=gaussian.latent_variance,
    )

    reference_stats = field_statistics(
        reference,
        target_mean=target.mean,
        target_standard_deviation=target.standard_deviation,
    )
    generated_stats = field_statistics(
        generated,
        target_mean=target.mean,
        target_standard_deviation=target.standard_deviation,
    )

    maximum_x_lag = 30
    maximum_z_lag = 15
    empirical_x = empirical_axis_correlation(
        reference,
        axis=0,
        maximum_lag=maximum_x_lag,
    )
    empirical_z = empirical_axis_correlation(
        reference,
        axis=1,
        maximum_lag=maximum_z_lag,
    )

    x_lags = np.arange(maximum_x_lag + 1, dtype=np.float64)
    z_lags = np.arange(maximum_z_lag + 1, dtype=np.float64)
    variance_x = float(exponential_cell_average_variance_factor(0.5, 10.0))
    variance_z = float(exponential_cell_average_variance_factor(0.5, 1.0))
    latent_variance = variance_x * variance_z
    covariance_x = exponential_cell_average_covariance_1d(x_lags * 0.5, 0.5, 10.0) * variance_z
    covariance_z = exponential_cell_average_covariance_1d(z_lags * 0.5, 0.5, 1.0) * variance_x
    log_parameters = lognormal_latent_parameters(
        target.mean,
        target.standard_deviation,
    )
    log_variance = log_parameters.standard_deviation_log**2
    denominator = math.expm1(log_variance * latent_variance)
    theoretical_x = np.expm1(log_variance * covariance_x) / denominator
    theoretical_z = np.expm1(log_variance * covariance_z) / denominator

    summary = {
        "matlab_reference": reference_stats.as_dict(),
        "python_realization": generated_stats.as_dict(),
        "spectral_diagnostics": asdict(prepared.diagnostics),
        "theoretical_infinite_spectrum_cell_variance_ratio": latent_variance,
        "theoretical_element_scale_coefficient_of_variation": math.sqrt(denominator),
    }
    (output_directory / "phase3_validation_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    np.savetxt(output_directory / "python_field_seed1403.csv", generated, delimiter=",")

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as error:  # pragma: no cover - optional dependency
        raise SystemExit("Install the validation extra: pip install -e '.[validation]'") from error

    figure = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "MATLAB reference field",
            "Corrected Python realization",
            "Physical-space marginal distribution",
            "Directional spatial correlation",
        ),
    )
    figure.add_trace(
        go.Heatmap(
            x=grid.x_centers,
            y=grid.z_centers,
            z=reference.T,
            coloraxis="coloraxis",
            name="MATLAB",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Heatmap(
            x=grid.x_centers,
            y=grid.z_centers,
            z=generated.T,
            coloraxis="coloraxis",
            name="Python",
        ),
        row=1,
        col=2,
    )
    figure.add_trace(
        go.Histogram(
            x=reference.ravel(),
            histnorm="probability density",
            nbinsx=60,
            opacity=0.55,
            name="MATLAB empirical",
        ),
        row=2,
        col=1,
    )
    element_log_std = log_parameters.standard_deviation_log * math.sqrt(latent_variance)
    element_log_mean = math.log(target.mean) - 0.5 * element_log_std**2
    x_pdf = np.linspace(float(reference.min()), float(reference.max()), 500)
    figure.add_trace(
        go.Scatter(
            x=x_pdf,
            y=lognorm.pdf(x_pdf, s=element_log_std, scale=math.exp(element_log_mean)),
            mode="lines",
            name="Theoretical averaged surrogate",
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=x_lags * 0.5, y=empirical_x, mode="lines+markers", name="Empirical x"),
        row=2,
        col=2,
    )
    figure.add_trace(
        go.Scatter(x=x_lags * 0.5, y=theoretical_x, mode="lines", name="Theory x"),
        row=2,
        col=2,
    )
    figure.add_trace(
        go.Scatter(x=z_lags * 0.5, y=empirical_z, mode="lines+markers", name="Empirical z"),
        row=2,
        col=2,
    )
    figure.add_trace(
        go.Scatter(x=z_lags * 0.5, y=theoretical_z, mode="lines", name="Theory z"),
        row=2,
        col=2,
    )
    figure.update_layout(
        title="RFieldMesh Phase 3 numerical validation",
        template="plotly_white",
        width=1300,
        height=900,
        coloraxis={
            "colorscale": "Viridis",
            "colorbar": {"title": "Young's modulus (Pa)"},
        },
        barmode="overlay",
    )
    figure.update_xaxes(title_text="x", row=1, col=1)
    figure.update_yaxes(title_text="z", row=1, col=1)
    figure.update_xaxes(title_text="x", row=1, col=2)
    figure.update_yaxes(title_text="z", row=1, col=2)
    figure.update_xaxes(title_text="Young's modulus (Pa)", row=2, col=1)
    figure.update_yaxes(title_text="Probability density", row=2, col=1)
    figure.update_xaxes(title_text="Separation distance", row=2, col=2)
    figure.update_yaxes(title_text="Correlation", row=2, col=2)
    figure.write_html(
        output_directory / "phase3_validation.html",
        include_plotlyjs=True,
        full_html=True,
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
