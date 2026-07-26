"""Shared synthetic Abaqus fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def small_inp(tmp_path: Path) -> Path:
    """Return a CRLF model with a target set inside a larger source section."""
    text = """*Heading
** synthetic Phase 4 fixture
*Part, name="Soil Part"
*Node
1, 0., 0.
2, 1., 0.
3, 2., 0.
4, 3., 0.
5, 0., 1.
6, 1., 1.
7, 2., 1.
8, 3., 1.
*Element, type=CPE4R
10, 1, 2, 6, 5
20, 2, 3, 7, 6
30, 3, 4, 8, 7
*Elset, elset=All
10, 20, 30
*Elset, elset=Target, generate
10, 20, 10
** Section: Soil
*Solid Section, elset=All, material=Soil
,
*End Part
*Assembly, name=Assembly
*Instance, name="Soil Part-1", part="Soil Part"
10., 20., 0.
*End Instance
*End Assembly
** MATERIALS
*Material, name=Soil
*Damping, alpha=0.1, beta=0.01
*Density
1800.,
*Elastic
2e7, 0.35
*Mohr Coulomb
25., 5.
*Mohr Coulomb Hardening
5000., 0.
** STEPS
*Step, name=Step-1
*Static
1., 1.
*End Step
"""
    path = tmp_path / "small.inp"
    path.write_bytes(text.replace("\n", "\r\n").encode("ascii"))
    return path
