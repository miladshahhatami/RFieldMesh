"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from rfieldmesh.config.enums import CorrelationKind, DistributionKind, PropertyKind
from rfieldmesh.config.models import (
    BatchConfig,
    BoundsConfig,
    CorrelationConfig,
    GenerationConfig,
    MomentSpecification,
    RandomVariableConfig,
)


def test_valid_variable_configuration() -> None:
    config = RandomVariableConfig(
        property_kind=PropertyKind.YOUNGS_MODULUS,
        moments=MomentSpecification(mean=20.0e6, standard_deviation=6.0e6),
        distribution=DistributionKind.LOGNORMAL,
        correlation=CorrelationConfig(
            model=CorrelationKind.EXPONENTIAL,
            scales=(10.0, 1.0),
        ),
    )
    assert config.moments.coefficient_of_variation == pytest.approx(0.3)


def test_truncated_normal_requires_bounds() -> None:
    with pytest.raises(ValidationError):
        RandomVariableConfig(
            property_kind=PropertyKind.DENSITY,
            moments=MomentSpecification(mean=1800.0, standard_deviation=180.0),
            distribution=DistributionKind.TRUNCATED_NORMAL,
            correlation=CorrelationConfig(scales=(10.0, 1.0)),
        )


def test_invalid_bounds_are_rejected() -> None:
    with pytest.raises(ValidationError):
        BoundsConfig(lower=5.0, upper=2.0)


def test_batch_config_requires_realization_dependent_inp_filename() -> None:
    variable = RandomVariableConfig(
        property_kind=PropertyKind.YOUNGS_MODULUS,
        moments=MomentSpecification(mean=20.0e6, standard_deviation=6.0e6),
        distribution=DistributionKind.LOGNORMAL,
        correlation=CorrelationConfig(scales=(10.0, 1.0)),
    )
    generation = GenerationConfig(
        source_path="source.inp",
        output_path="ignored.inp",
        part_name="Soil",
        set_name="Target",
        variables=(variable,),
    )
    with pytest.raises(ValidationError, match="include"):
        BatchConfig(
            generation=generation,
            output_directory="outputs",
            filename_template="constant.inp",
        )
    with pytest.raises(ValidationError, match="end in"):
        BatchConfig(
            generation=generation,
            output_directory="outputs",
            filename_template="case_{index}.txt",
        )
