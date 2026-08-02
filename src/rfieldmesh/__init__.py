"""Numerical core for mesh-based spatial random fields."""

from importlib.metadata import PackageNotFoundError, version

from rfieldmesh.config.enums import (
    CorrelationKind,
    DistributionKind,
    GenerationAlgorithm,
    MappingMethod,
    PropertyKind,
    SeedStrategy,
)
from rfieldmesh.config.models import (
    BatchConfig,
    BoundsConfig,
    CorrelationConfig,
    GenerationConfig,
    KLConfig,
    MomentSpecification,
    RandomVariableConfig,
    SpectralConfig,
)
from rfieldmesh.config.properties import (
    PROPERTY_REGISTRY,
    PropertyDefinition,
    property_definition,
)
from rfieldmesh.random_fields.covariance_kl import PreparedCovarianceKL
from rfieldmesh.random_fields.marginals import apply_marginal
from rfieldmesh.random_fields.observations import StructuredGrid2D
from rfieldmesh.random_fields.rng import rng_for_realization
from rfieldmesh.random_fields.spectral import PreparedSpectralExponential2D
from rfieldmesh.random_fields.statistics import FieldStatistics, field_statistics

try:
    __version__ = version("rfieldmesh")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0+unknown"

__all__ = [
    "PROPERTY_REGISTRY",
    "BatchConfig",
    "BoundsConfig",
    "CorrelationConfig",
    "CorrelationKind",
    "DistributionKind",
    "FieldStatistics",
    "GenerationAlgorithm",
    "GenerationConfig",
    "KLConfig",
    "MappingMethod",
    "MomentSpecification",
    "PreparedCovarianceKL",
    "PreparedSpectralExponential2D",
    "PropertyDefinition",
    "PropertyKind",
    "RandomVariableConfig",
    "SeedStrategy",
    "SpectralConfig",
    "StructuredGrid2D",
    "apply_marginal",
    "field_statistics",
    "property_definition",
    "rng_for_realization",
]
