"""Stable enumerations used in configuration and manifests."""

from enum import StrEnum


class PropertyKind(StrEnum):
    """Material properties supported by the first release."""

    YOUNGS_MODULUS = "youngs_modulus"
    DENSITY = "density"


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
