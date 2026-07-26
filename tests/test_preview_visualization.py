"""Unsaved preview and Plotly report tests."""

import hashlib
from pathlib import Path

from rfieldmesh.application.preview import preview_model
from rfieldmesh.config.enums import DistributionKind, PropertyKind
from rfieldmesh.config.models import (
    CorrelationConfig,
    GenerationConfig,
    MomentSpecification,
    RandomVariableConfig,
)
from rfieldmesh.visualization.figures import (
    distribution_figure,
    export_preview_html,
    field_figure,
    preview_html,
)


def preview_config(source: Path, output: Path) -> GenerationConfig:
    """Return a compact deterministic preview request."""
    return GenerationConfig(
        source_path=str(source),
        output_path=str(output),
        part_name="Soil Part",
        set_name="Target",
        variables=(
            RandomVariableConfig(
                property_kind=PropertyKind.YOUNGS_MODULUS,
                moments=MomentSpecification(
                    mean=2.0e7,
                    standard_deviation=4.0e6,
                    unit_label="Pa",
                ),
                distribution=DistributionKind.LOGNORMAL,
                correlation=CorrelationConfig(scales=(2.0, 1.0)),
            ),
        ),
    )


def test_preview_generates_without_writing_abaqus(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "must_not_exist.inp"
    result = preview_model(preview_config(small_inp, output))
    assert result.eligible_count == 2
    assert result.excluded_count == 0
    assert len(result.fields[0].values) == 2
    assert not output.exists()


def test_visualization_builds_spatial_distribution_and_offline_html(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    result = preview_model(preview_config(small_inp, tmp_path / "unused.inp"))
    spatial = field_figure(result)
    distribution = distribution_figure(result)
    assert spatial.data[0].type == "heatmap"
    assert {trace.type for trace in distribution.data} == {"histogram", "scatter"}

    rendered = preview_html(result)
    assert "plotly.js" in rendered
    assert "RFieldMesh realization preview" in rendered
    assert "Eligible: 2" in rendered

    output = tmp_path / "preview.html"
    checksum = export_preview_html(result, output)
    assert len(checksum) == 64
    exported = output.read_text(encoding="utf-8")
    assert "RFieldMesh realization preview" in exported
    assert checksum == hashlib.sha256(output.read_bytes()).hexdigest()
