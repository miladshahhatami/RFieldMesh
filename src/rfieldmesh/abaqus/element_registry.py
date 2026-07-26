"""Explicit eligibility registry for supported first-order continuum elements."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ElementDescriptor:
    """Geometry and eligibility metadata for one element type."""

    element_type: str
    dimension: int
    node_count: int
    supported: bool
    representative_point: str


_SUPPORTED: dict[str, ElementDescriptor] = {
    element_type: ElementDescriptor(
        element_type=element_type,
        dimension=dimension,
        node_count=node_count,
        supported=True,
        representative_point="isoparametric_center",
    )
    for element_type, dimension, node_count in (
        ("CPE3", 2, 3),
        ("CPE4", 2, 4),
        ("CPE4R", 2, 4),
        ("CPS3", 2, 3),
        ("CPS4", 2, 4),
        ("CPS4R", 2, 4),
        ("CAX3", 2, 3),
        ("CAX4", 2, 4),
        ("CAX4R", 2, 4),
        ("C3D4", 3, 4),
        ("C3D8", 3, 8),
        ("C3D8R", 3, 8),
    )
}


def element_descriptor(element_type: str) -> ElementDescriptor:
    """Return explicit support metadata, including a reasoned unsupported default."""
    normalized = element_type.strip().upper()
    if normalized in _SUPPORTED:
        return _SUPPORTED[normalized]
    dimension = 3 if "3D" in normalized else 2
    return ElementDescriptor(
        element_type=normalized,
        dimension=dimension,
        node_count=0,
        supported=False,
        representative_point="unsupported",
    )


def supported_element_types() -> tuple[str, ...]:
    """Return the stable MVP eligibility list."""
    return tuple(_SUPPORTED)
