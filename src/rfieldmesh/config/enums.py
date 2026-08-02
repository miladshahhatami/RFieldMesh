"""Stable enumerations used in configuration and manifests."""

from enum import StrEnum


class PropertyKind(StrEnum):
    """Material properties supported by RFieldMesh v1.0.0.

    ``youngs_modulus`` was used by pre-publication configuration files. It is
    accepted through :meth:`_missing_`, while new manifests use the clearer
    ``elastic_modulus`` identifier.
    """

    ELASTIC_MODULUS = "elastic_modulus"
    YOUNGS_MODULUS = "elastic_modulus"  # backwards-compatible Python alias
    DENSITY = "density"
    POISSONS_RATIO = "poissons_ratio"
    FRICTION_ANGLE = "friction_angle"
    DILATION_ANGLE = "dilation_angle"

    @classmethod
    def _missing_(cls, value: object) -> "PropertyKind | None":
        if isinstance(value, str) and value.casefold() == "youngs_modulus":
            return cls.ELASTIC_MODULUS
        return None


class DistributionKind(StrEnum):
    """Supported physical-space marginal distributions."""

    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    TRUNCATED_NORMAL = "truncated_normal"


class CorrelationKind(StrEnum):
    """Supported latent-Gaussian autocorrelation models."""

    EXPONENTIAL = "exponential"
    SQUARED_EXPONENTIAL = "squared_exponential"


class MappingMethod(StrEnum):
    """Observation operators implemented by the Phase 3 prototype."""

    AUTO = "auto"
    CENTROID_SAMPLE = "centroid_sample"
    RECTANGULAR_GAUSSIAN_AVERAGE = "rectangular_gaussian_average"


class SeedStrategy(StrEnum):
    """Realization-level seed derivation strategies."""

    LINEAR = "linear"
    SPAWN = "spawn"


class GenerationAlgorithm(StrEnum):
    """Random-field methods available to the Phase 4 application workflow."""

    AUTO = "auto"
    SPECTRAL = "spectral"
    COVARIANCE_KL = "covariance_kl"
