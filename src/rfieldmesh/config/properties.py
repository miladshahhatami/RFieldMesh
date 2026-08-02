"""Central metadata and validation rules for Abaqus material properties."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from rfieldmesh.config.enums import DistributionKind, PropertyKind
from rfieldmesh.exceptions import ConfigurationError

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class PropertyDefinition:
    """One supported scalar value within an Abaqus material keyword row."""

    kind: PropertyKind
    display_name: str
    symbol: str
    unit_convention: str
    abaqus_keyword: str
    column_index: int
    minimum: float | None
    maximum: float | None
    minimum_inclusive: bool
    maximum_inclusive: bool
    default_mean: float
    default_cv: float
    default_unit: str
    default_distribution: DistributionKind
    supported_distributions: tuple[DistributionKind, ...] = (
        DistributionKind.NORMAL,
        DistributionKind.LOGNORMAL,
        DistributionKind.TRUNCATED_NORMAL,
    )
    number_format: str = ".15g"
    default_lower: float | None = None
    default_upper: float | None = None

    def value_is_valid(self, value: float) -> bool:
        """Return whether a finite scalar satisfies the admissible interval."""
        if not np.isfinite(value):
            return False
        if self.minimum is not None and (
            value < self.minimum or (value == self.minimum and not self.minimum_inclusive)
        ):
            return False
        return not (
            self.maximum is not None
            and (value > self.maximum or (value == self.maximum and not self.maximum_inclusive))
        )

    def format_value(self, value: float) -> str:
        """Format an Abaqus scalar according to the registry rule."""
        return format(value, self.number_format)

    @property
    def interval_text(self) -> str:
        left = "[" if self.minimum_inclusive else "("
        right = "]" if self.maximum_inclusive else ")"
        lower = "-inf" if self.minimum is None else f"{self.minimum:g}"
        upper = "+inf" if self.maximum is None else f"{self.maximum:g}"
        return f"{left}{lower}, {upper}{right}"


PROPERTY_REGISTRY: dict[PropertyKind, PropertyDefinition] = {
    PropertyKind.ELASTIC_MODULUS: PropertyDefinition(
        PropertyKind.ELASTIC_MODULUS,
        "Young's modulus",
        "E",
        "Abaqus model-consistent stress unit",
        "elastic",
        0,
        0.0,
        None,
        False,
        False,
        20_000_000.0,
        0.30,
        "Pa",
        DistributionKind.LOGNORMAL,
    ),
    PropertyKind.DENSITY: PropertyDefinition(
        PropertyKind.DENSITY,
        "Density",
        "rho",
        "Abaqus model-consistent mass density unit",
        "density",
        0,
        0.0,
        None,
        False,
        False,
        1800.0,
        0.10,
        "kg/m^3",
        DistributionKind.LOGNORMAL,
    ),
    PropertyKind.POISSONS_RATIO: PropertyDefinition(
        PropertyKind.POISSONS_RATIO,
        "Poisson's ratio",
        "nu",
        "dimensionless",
        "elastic",
        1,
        -1.0,
        0.5,
        False,
        False,
        0.35,
        0.08,
        "",
        DistributionKind.TRUNCATED_NORMAL,
        default_lower=0.05,
        default_upper=0.49,
    ),
    PropertyKind.FRICTION_ANGLE: PropertyDefinition(
        PropertyKind.FRICTION_ANGLE,
        "Friction angle",
        "phi",
        "degrees",
        "mohr coulomb",
        0,
        0.0,
        90.0,
        False,
        False,
        25.0,
        0.10,
        "deg",
        DistributionKind.TRUNCATED_NORMAL,
        default_lower=1.0e-9,
        default_upper=89.999,
    ),
    PropertyKind.DILATION_ANGLE: PropertyDefinition(
        PropertyKind.DILATION_ANGLE,
        "Dilation angle",
        "psi",
        "degrees",
        "mohr coulomb",
        1,
        0.0,
        90.0,
        True,
        False,
        5.0,
        0.20,
        "deg",
        DistributionKind.TRUNCATED_NORMAL,
        default_lower=0.0,
        default_upper=89.999,
    ),
}


def property_definition(kind: PropertyKind | str) -> PropertyDefinition:
    """Resolve registry metadata while accepting the legacy modulus identifier."""
    return PROPERTY_REGISTRY[PropertyKind(kind)]


def validate_property_values(
    kind: PropertyKind | str,
    values: FloatArray,
    *,
    context: str = "generated field",
) -> FloatArray:
    """Reject, rather than clip, values outside a property's admissible range."""
    definition = property_definition(kind)
    array = np.asarray(values, dtype=np.float64)
    valid = np.fromiter(
        (definition.value_is_valid(float(value)) for value in array.flat),
        dtype=bool,
        count=array.size,
    ).reshape(array.shape)
    if not np.all(valid):
        invalid = array[~valid]
        sample = ", ".join(f"{value:.8g}" for value in invalid[:5])
        raise ConfigurationError(
            f"{definition.display_name} {context} contains {invalid.size} value(s) outside "
            f"the admissible interval {definition.interval_text}; examples: {sample}. "
            "Use a bounded distribution or revise the statistics. Values were not clipped."
        )
    return array
