"""Generate one mean-corrected locally averaged lognormal field."""

import numpy as np

from rfieldmesh import (
    DistributionKind,
    MappingMethod,
    MomentSpecification,
    PreparedSpectralExponential2D,
    PropertyKind,
    SpectralConfig,
    StructuredGrid2D,
    apply_marginal,
    field_statistics,
    rng_for_realization,
)

grid = StructuredGrid2D(
    x_nodes=np.arange(0.0, 100.0 + 0.25, 0.5),
    z_nodes=np.arange(0.0, 50.0 + 0.25, 0.5),
)
prepared = PreparedSpectralExponential2D.prepare(
    grid,
    scales=(10.0, 1.0),
    mapping=MappingMethod.RECTANGULAR_GAUSSIAN_AVERAGE,
    config=SpectralConfig(retained_variance=0.99999),
)
rng = rng_for_realization(1403, 0, PropertyKind.YOUNGS_MODULUS)
latent = prepared.generate(rng)
moments = MomentSpecification(
    mean=20_000_000.0,
    standard_deviation=6_000_000.0,
    unit_label="Pa",
)
youngs_modulus = apply_marginal(
    latent.values,
    moments,
    DistributionKind.LOGNORMAL,
    latent_variance=latent.latent_variance,
)
print(
    field_statistics(
        youngs_modulus,
        target_mean=moments.mean,
        target_standard_deviation=moments.standard_deviation,
    )
)
