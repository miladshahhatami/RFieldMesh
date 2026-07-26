"""End-to-end application-service tests."""

import json
from pathlib import Path

from rfieldmesh.application.generate import generate_model
from rfieldmesh.application.inspect_model import inspect_model
from rfieldmesh.config.enums import DistributionKind, PropertyKind
from rfieldmesh.config.models import (
    CorrelationConfig,
    GenerationConfig,
    MomentSpecification,
    RandomVariableConfig,
)


def test_inspection_summary_is_json_serializable(small_inp: Path) -> None:
    summary = inspect_model(small_inp)
    assert summary["parts"][0]["element_count"] == 3
    assert summary["instances"][0]["transformation"][0][3] == 10.0
    json.dumps(summary)


def test_end_to_end_generation_writes_manifest_and_validates(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "randomized.inp"
    config = GenerationConfig(
        source_path=str(small_inp),
        output_path=str(output),
        part_name="Soil Part",
        set_name="Target",
        variables=(
            RandomVariableConfig(
                property_kind=PropertyKind.YOUNGS_MODULUS,
                moments=MomentSpecification(
                    mean=2.0e7,
                    standard_deviation=4.0e6,
                ),
                distribution=DistributionKind.LOGNORMAL,
                correlation=CorrelationConfig(scales=(2.0, 1.0)),
            ),
        ),
    )
    result = generate_model(config)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.validation.checked_elements == 2
    assert output.exists()
    assert manifest["output"]["sha256"] == result.assignment.output_sha256
    assert manifest["source"]["filename"] == small_inp.name
    assert "path" not in manifest["source"]
    assert manifest["configuration"]["source_path"] == small_inp.name
    assert manifest["fields"][0]["algorithm"] == "spectral"
    assert manifest["region"]["section_remainder_count"] == 1
    assert len(manifest["assignment"]["material_names_by_element"]) == 2
    assert len(manifest["assignment"]["set_names_by_element"]) == 2
