"""Lexical token models for Abaqus keyword files."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


def canonical_name(value: str) -> str:
    """Return a case-insensitive lookup key while preserving significant spaces."""
    return value.strip().strip('"').casefold()


@dataclass(frozen=True, slots=True)
class KeywordToken:
    """One Abaqus keyword header and its following data span."""

    index: int
    keyword: str
    raw_keyword: str
    parameters: Mapping[str, str | None]
    start: int
    header_end: int
    data_start: int
    data_end: int

    def parameter(self, name: str) -> str | None:
        """Return a case-insensitive parameter value."""
        return self.parameters.get(name.casefold())


def readonly_parameters(values: dict[str, str | None]) -> Mapping[str, str | None]:
    """Expose parsed header parameters without allowing mutation."""
    return MappingProxyType(values)
