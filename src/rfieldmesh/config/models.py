"""Pydantic configuration models for the numerical core."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rfieldmesh.config.enums import (
    CorrelationKind,
    DistributionKind,
    GenerationAlgorithm,
    MappingMethod,
    PropertyKind,
    SeedStrategy,
)


class FrozenModel(BaseModel):
    """Strict, immutable base model."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class MomentSpecification(FrozenModel):
    """Physical-space point statistics for a positive material property."""

    mean: float = Field(gt=0.0)
    standard_deviation: float = Field(gt=0.0)
    unit_label: str = ""

    @field_validator("mean", "standard_deviation")
    @classmethod
    def require_finite(cls, value: float) -> float:
        """Reject NaN and infinite material statistics."""
        if not math.isfinite(value):
            raise ValueError("Material statistics must be finite.")
        return value

    @property
    def coefficient_of_variation(self) -> float:
        """Return the point-scale physical coefficient of variation."""
        return self.standard_deviation / self.mean


class BoundsConfig(FrozenModel):
    """Optional physical-space bounds."""

    lower: float | None = None
    upper: float | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> BoundsConfig:
        """Require finite, ordered bounds when supplied."""
        for value in (self.lower, self.upper):
            if value is not None and not math.isfinite(value):
                raise ValueError("Finite bounds are required when a bound is supplied.")
        if self.lower is None and self.upper is None:
            raise ValueError("At least one truncated-normal bound is required.")
        if self.lower is not None and self.upper is not None and self.lower >= self.upper:
            raise ValueError("The lower bound must be smaller than the upper bound.")
        return self


class CorrelationConfig(FrozenModel):
    """Latent-Gaussian correlation definition."""

    model: CorrelationKind = CorrelationKind.EXPONENTIAL
    scales: tuple[float, ...]

    @field_validator("scales")
    @classmethod
    def validate_scales(cls, scales: tuple[float, ...]) -> tuple[float, ...]:
        """Accept only positive finite scales in two or three dimensions."""
        if len(scales) not in (2, 3):
            raise ValueError("Exactly two or three directional scales are required.")
        if any(not math.isfinite(value) or value <= 0.0 for value in scales):
            raise ValueError("Every directional scale must be positive and finite.")
        return scales


class SpectralConfig(FrozenModel):
    """Numerical controls for the Fourier spectral algorithm."""

    retained_variance: float = Field(default=0.99999, gt=0.0, le=1.0)
    padding_scale: float = Field(default=4.0, gt=0.0)
    max_mode_cap: int = Field(default=100_000, ge=8)
    max_coefficient_count: int = Field(default=10_000_000, ge=1)
    legacy_relative_threshold: float | None = Field(default=None, gt=0.0)


class KLConfig(FrozenModel):
    """Numerical controls for covariance/Karhunen-Loeve simulation."""

    retained_variance: float = Field(default=0.999, gt=0.0, le=1.0)
    eigenvalue_tolerance: float = Field(default=1.0e-10, gt=0.0)
    max_points: int = Field(default=5_000, ge=2)
    normalize_point_variance: bool = True


class RandomVariableConfig(FrozenModel):
    """Complete Phase 3 definition of one independent material field."""

    property_kind: PropertyKind
    moments: MomentSpecification
    distribution: DistributionKind
    correlation: CorrelationConfig
    bounds: BoundsConfig | None = None
    seed: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_distribution_and_bounds(self) -> RandomVariableConfig:
        """Require bounds only for the truncated-normal implementation."""
        if self.distribution is DistributionKind.TRUNCATED_NORMAL and self.bounds is None:
            raise ValueError("Truncated-normal fields require at least one physical bound.")
        if self.distribution is not DistributionKind.TRUNCATED_NORMAL and self.bounds is not None:
            raise ValueError("Bounds require distribution='truncated_normal' in Phase 3.")
        return self


class GenerationConfig(FrozenModel):
    """Serializable Phase 4 end-to-end generation request."""

    source_path: str
    output_path: str
    part_name: str
    set_name: str
    instance_name: str | None = None
    variables: tuple[RandomVariableConfig, ...]
    first_seed: int = Field(default=1403, ge=0)
    realization_index: int = Field(default=0, ge=0)
    seed_strategy: SeedStrategy = SeedStrategy.LINEAR
    algorithm: GenerationAlgorithm = GenerationAlgorithm.AUTO
    mapping: MappingMethod = MappingMethod.AUTO
    spectral: SpectralConfig = SpectralConfig()
    covariance_kl: KLConfig = KLConfig()
    name_prefix: str = Field(default="RFM", min_length=1, max_length=32)
    overwrite: bool = False
    manifest_path: str | None = None

    @field_validator("variables")
    @classmethod
    def validate_variables(
        cls,
        variables: tuple[RandomVariableConfig, ...],
    ) -> tuple[RandomVariableConfig, ...]:
        if not variables:
            raise ValueError("At least one random material property is required.")
        kinds = [variable.property_kind for variable in variables]
        if len(set(kinds)) != len(kinds):
            raise ValueError("Each material property may be configured only once per region.")
        return variables


class BatchConfig(FrozenModel):
    """Multi-realization generation request built around one generation template."""

    generation: GenerationConfig
    output_directory: str
    realization_count: int = Field(default=1, ge=1, le=100_000)
    start_index: int = Field(default=0, ge=0)
    filename_template: str = Field(
        default="RFieldMesh_{index:04d}_seed{seed}.inp",
        min_length=5,
        max_length=180,
    )
    summary_path: str | None = None
    continue_on_error: bool = False

    @field_validator("filename_template")
    @classmethod
    def validate_filename_template(cls, template: str) -> str:
        """Reject directory traversal and require a realization-dependent name."""
        if "/" in template or "\\" in template:
            raise ValueError("The batch filename template must contain a filename only.")
        if not template.casefold().endswith(".inp"):
            raise ValueError("The batch filename template must end in '.inp'.")
        if "{index" not in template and "{seed" not in template:
            raise ValueError("The batch filename template must include {index} or {seed}.")
        try:
            rendered = template.format(index=0, realization=0, seed=0)
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(
                "Batch filenames may use only {index}, {realization}, and {seed}."
            ) from exc
        if rendered in {"", ".", ".."}:
            raise ValueError("The batch filename template produces an invalid filename.")
        return template
