"""Patch writer and independent output-validation tests."""

from pathlib import Path

from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import resolve_region
from rfieldmesh.abaqus.validation import validate_generated_output
from rfieldmesh.abaqus.writer import write_elementwise_materials


def test_writer_clones_complete_material_and_splits_remainder(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    model = parse_abaqus_model(small_inp)
    region = resolve_region(model, part_name="Soil Part", set_name="Target")
    output = tmp_path / "generated.inp"
    youngs = {10: 1.8e7, 20: 2.2e7}
    densities = {10: 1750.0, 20: 1850.0}
    result = write_elementwise_materials(
        model,
        region,
        output,
        youngs_modulus=youngs,
        density=densities,
    )
    validation = validate_generated_output(
        result,
        expected_youngs_modulus=youngs,
        expected_density=densities,
    )
    generated_text = output.read_text(encoding="ascii")
    assert validation.valid
    assert validation.remainder_count == 1
    assert generated_text.count("*Damping, alpha=0.1, beta=0.01") == 3
    assert generated_text.count("*Mohr Coulomb Hardening") == 3
    assert "*Solid Section, elset=RFM_REMAINDER, material=Soil" in generated_text


def test_writer_leaves_source_bytes_unchanged(small_inp: Path, tmp_path: Path) -> None:
    before = small_inp.read_bytes()
    model = parse_abaqus_model(small_inp)
    region = resolve_region(model, part_name="Soil Part", set_name="Target")
    write_elementwise_materials(
        model,
        region,
        tmp_path / "generated.inp",
        youngs_modulus={10: 1.9e7, 20: 2.1e7},
    )
    assert small_inp.read_bytes() == before
