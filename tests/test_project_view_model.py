"""Qt-independent desktop presentation-state tests."""

from pathlib import Path

from rfieldmesh.config.enums import DistributionKind, PropertyKind
from rfieldmesh.config.models import (
    CorrelationConfig,
    GenerationConfig,
    MomentSpecification,
    RandomVariableConfig,
)
from rfieldmesh.gui.project_view_model import ProjectViewModel


def test_view_model_loads_choices_and_creates_preview(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    view_model = ProjectViewModel()
    inspection = view_model.load_model(small_inp)
    assert inspection["parts"][0]["name"] == "Soil Part"
    options = view_model.part_options()
    assert options[0].element_sets == ("All", "Target")
    assert options[0].instances == ("Soil Part-1",)

    config = GenerationConfig(
        source_path=str(small_inp),
        output_path=str(tmp_path / "unused.inp"),
        part_name="Soil Part",
        set_name="Target",
        variables=(
            RandomVariableConfig(
                property_kind=PropertyKind.YOUNGS_MODULUS,
                moments=MomentSpecification(mean=2.0e7, standard_deviation=4.0e6),
                distribution=DistributionKind.LOGNORMAL,
                correlation=CorrelationConfig(scales=(2.0, 1.0)),
            ),
        ),
    )
    preview, rendered = view_model.create_preview(config)
    assert view_model.preview_result is preview
    assert "RFieldMesh realization preview" in rendered
