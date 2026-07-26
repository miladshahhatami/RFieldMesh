"""Deterministic modern NumPy random-number streams."""

from __future__ import annotations

import numpy as np

from rfieldmesh.config.enums import PropertyKind, SeedStrategy
from rfieldmesh.exceptions import ConfigurationError

_PROPERTY_STREAM_CODES: dict[PropertyKind, int] = {
    PropertyKind.YOUNGS_MODULUS: 101,
    PropertyKind.DENSITY: 211,
}


def property_stream_code(property_kind: PropertyKind) -> int:
    """Return a stable, documented stream identifier."""
    return _PROPERTY_STREAM_CODES[property_kind]


def rng_for_realization(
    first_seed: int,
    realization_index: int,
    property_kind: PropertyKind,
    strategy: SeedStrategy = SeedStrategy.LINEAR,
) -> np.random.Generator:
    """Construct a scheduling-order-independent PCG64DXSM generator.

    Parameters
    ----------
    first_seed:
        Nonnegative root or first realization seed.
    realization_index:
        Zero-based realization index.
    property_kind:
        Stable stream discriminator. Adding another material field does not
        change the stream for an existing property.
    strategy:
        ``linear`` uses ``first_seed + realization_index`` as the displayed
        realization seed. ``spawn`` uses a hierarchical spawn key.
    """
    if first_seed < 0 or realization_index < 0:
        raise ConfigurationError("Seeds and realization indices must be nonnegative.")

    stream_code = property_stream_code(property_kind)
    if strategy is SeedStrategy.LINEAR:
        seed_sequence = np.random.SeedSequence([first_seed + realization_index, stream_code])
    elif strategy is SeedStrategy.SPAWN:
        seed_sequence = np.random.SeedSequence(
            entropy=first_seed,
            spawn_key=(realization_index, stream_code),
        )
    else:  # pragma: no cover - protected by the enum type
        raise ConfigurationError(f"Unsupported seed strategy: {strategy!r}")
    return np.random.Generator(np.random.PCG64DXSM(seed_sequence))
