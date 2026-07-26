"""Random-stream reproducibility tests."""

import numpy as np

from rfieldmesh.config.enums import PropertyKind, SeedStrategy
from rfieldmesh.random_fields.rng import rng_for_realization


def test_identical_stream_definition_reproduces_values() -> None:
    first = rng_for_realization(1403, 0, PropertyKind.YOUNGS_MODULUS)
    second = rng_for_realization(1403, 0, PropertyKind.YOUNGS_MODULUS)
    assert np.array_equal(first.standard_normal(20), second.standard_normal(20))


def test_property_streams_and_realizations_differ() -> None:
    youngs = rng_for_realization(1403, 0, PropertyKind.YOUNGS_MODULUS)
    density = rng_for_realization(1403, 0, PropertyKind.DENSITY)
    next_youngs = rng_for_realization(1403, 1, PropertyKind.YOUNGS_MODULUS)
    assert not np.array_equal(youngs.standard_normal(10), density.standard_normal(10))
    assert not np.array_equal(
        rng_for_realization(1403, 0, PropertyKind.YOUNGS_MODULUS).standard_normal(10),
        next_youngs.standard_normal(10),
    )


def test_spawn_strategy_is_reproducible() -> None:
    first = rng_for_realization(
        1403,
        7,
        PropertyKind.DENSITY,
        SeedStrategy.SPAWN,
    )
    second = rng_for_realization(
        1403,
        7,
        PropertyKind.DENSITY,
        SeedStrategy.SPAWN,
    )
    assert np.array_equal(first.integers(0, 100, 30), second.integers(0, 100, 30))
