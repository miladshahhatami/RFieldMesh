"""Reproduce Phase 5 preview, batch, and packaging acceptance checks."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from rfieldmesh import __version__
from rfieldmesh.application.batch import run_batch
from rfieldmesh.application.preview import PreviewResult, preview_model
from rfieldmesh.config.enums import DistributionKind, PropertyKind
from rfieldmesh.config.models import (
    BatchConfig,
    CorrelationConfig,
    GenerationConfig,
    KLConfig,
    MomentSpecification,
    RandomVariableConfig,
)
from rfieldmesh.infrastructure.atomic_files import write_json_atomic, write_text_atomic
from rfieldmesh.visualization.figures import distribution_figure, field_figure


def _config(
    source: Path,
    *,
    part: str,
    element_set: str,
    scales: tuple[float, ...],
    output: Path,
) -> GenerationConfig:
    return GenerationConfig(
        source_path=str(source),
        output_path=str(output),
        part_name=part,
        set_name=element_set,
        variables=(
            RandomVariableConfig(
                property_kind=PropertyKind.YOUNGS_MODULUS,
                moments=MomentSpecification(
                    mean=20_000_000.0,
                    standard_deviation=6_000_000.0,
                    unit_label="Pa",
                ),
                distribution=DistributionKind.LOGNORMAL,
                correlation=CorrelationConfig(scales=scales),
            ),
        ),
        first_seed=1403,
        covariance_kl=KLConfig(retained_variance=0.999),
    )


def _preview_summary(preview: PreviewResult, elapsed: float) -> dict[str, Any]:
    field = preview.fields[0]
    return {
        "source_filename": preview.model.source.path.name,
        "part": preview.region.part.name,
        "set": preview.region.set_name,
        "dimension": preview.region.dimension,
        "selected_count": len(preview.region.selected_labels),
        "eligible_count": preview.eligible_count,
        "excluded_by_type": {
            name: len(labels) for name, labels in preview.region.excluded_by_type.items()
        },
        "algorithm": field.algorithm.value,
        "statistics": field.statistics.as_dict(),
        "elapsed_seconds": elapsed,
    }


def _figure_html(preview: PreviewResult, *, include_plotlyjs: str | bool) -> tuple[str, bool]:
    field = field_figure(preview)
    distribution = distribution_figure(preview)
    sections = [
        field.to_html(
            full_html=False,
            include_plotlyjs=include_plotlyjs,
            config={"responsive": True, "displaylogo": False},
        ),
        distribution.to_html(
            full_html=False,
            include_plotlyjs=False,
            config={"responsive": True, "displaylogo": False},
        ),
    ]
    return "".join(sections), False


def _qt_status() -> dict[str, Any]:
    available = importlib.util.find_spec("PySide6") is not None
    if not available:
        return {"python_package_available": False, "runtime_loadable": False}
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except ImportError as exc:
        return {
            "python_package_available": True,
            "runtime_loadable": False,
            "reason": str(exc),
        }
    return {"python_package_available": True, "runtime_loadable": True}


def _report_html(summary: dict[str, Any], sections: str) -> str:
    two_d = summary["preview_2d"]
    three_d = summary["preview_3d"]
    batch = summary["batch"]
    two_d_cv = two_d["statistics"]["sample_coefficient_of_variation"]
    three_d_counts = f"{three_d['selected_count']:,} / {three_d['eligible_count']:,}"
    three_d_excluded = html.escape(json.dumps(three_d["excluded_by_type"]))
    batch_counts = f"{batch['completed_count']} / {batch['requested_count']}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RFieldMesh Phase 5 validation</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 26px; color: #1f2933; }}
h1, h2 {{ color: #173f5f; }}
table {{ border-collapse: collapse; width: 100%; max-width: 950px; }}
th, td {{ border: 1px solid #d9e2ec; padding: 8px 10px; text-align: left; }}
th {{ background: #f0f4f8; }}
.pass {{ color: #147d64; font-weight: 600; }}
.plotly-graph-div {{ margin: 24px auto 38px; }}
code {{ background: #f0f4f8; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>RFieldMesh Phase 5 validation</h1>
<p class="pass">Preview, visualization, batch generation, and packaging-asset checks passed.</p>
<table>
<tr><th>Application version</th><td>{html.escape(str(summary["application_version"]))}</td></tr>
<tr><th>2D eligible elements</th><td>{two_d["eligible_count"]:,}</td></tr>
<tr><th>2D algorithm</th><td>{html.escape(str(two_d["algorithm"]))}</td></tr>
<tr><th>2D sample CV</th><td>{two_d_cv:.6f}</td></tr>
<tr><th>3D selected / eligible</th><td>{three_d_counts}</td></tr>
<tr><th>3D excluded</th><td>{three_d_excluded}</td></tr>
<tr><th>Batch completed</th><td>{batch_counts}</td></tr>
<tr><th>Windows packaging assets</th><td>{summary["packaging_assets_present"]}</td></tr>
</table>
<h2>Interactive field validation</h2>
{sections}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-2d", type=Path, required=True)
    parser.add_argument("--model-3d", type=Path, required=True)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("validation/output"),
    )
    arguments = parser.parse_args()
    model_2d = arguments.model_2d.expanduser().resolve()
    model_3d = arguments.model_3d.expanduser().resolve()
    output_directory = arguments.output_directory.expanduser().resolve()

    with tempfile.TemporaryDirectory(prefix="rfieldmesh-phase5-") as temporary:
        workspace = Path(temporary)
        config_2d = _config(
            model_2d,
            part="Part-1",
            element_set="Set-1",
            scales=(10.0, 1.0),
            output=workspace / "unused_2d.inp",
        )
        started = time.perf_counter()
        preview_2d = preview_model(config_2d)
        elapsed_2d = time.perf_counter() - started

        config_3d = _config(
            model_3d,
            part="Layered Soil Quarter",
            element_set="Layer1",
            scales=(10.0, 10.0, 4.0),
            output=workspace / "unused_3d.inp",
        )
        started = time.perf_counter()
        preview_3d = preview_model(config_3d)
        elapsed_3d = time.perf_counter() - started

        batch_config = BatchConfig(
            generation=config_3d,
            output_directory=str(workspace / "batch"),
            realization_count=2,
            filename_template="validation_{index}_seed{seed}.inp",
        )
        started = time.perf_counter()
        batch = run_batch(batch_config)
        elapsed_batch = time.perf_counter() - started
        batch_summary = {
            "requested_count": batch.requested_count,
            "completed_count": batch.completed_count,
            "failed_count": batch.failed_count,
            "cancelled": batch.cancelled,
            "elapsed_seconds": elapsed_batch,
            "output_sha256": [item.output_sha256 for item in batch.items],
            "checked_elements": [item.checked_elements for item in batch.items],
        }

    project_root = Path(__file__).resolve().parents[1]
    packaging_assets = (
        project_root / "packaging" / "pyinstaller" / "rfieldmesh-gui.spec",
        project_root / "packaging" / "windows" / "build.ps1",
        project_root / ".github" / "workflows" / "windows-build.yml",
    )
    summary = {
        "application_version": __version__,
        "preview_2d": _preview_summary(preview_2d, elapsed_2d),
        "preview_3d": _preview_summary(preview_3d, elapsed_3d),
        "batch": batch_summary,
        "qt": _qt_status(),
        "packaging_assets_present": all(path.is_file() for path in packaging_assets),
    }
    if batch.completed_count != 2 or batch.failed_count:
        raise RuntimeError("Phase 5 batch validation failed.")
    if preview_2d.eligible_count != 20_000:
        raise RuntimeError("The supplied 2D model did not resolve 20,000 elements.")
    if preview_3d.eligible_count != 108 or preview_3d.excluded_count != 30:
        raise RuntimeError("The supplied 3D mixed-element eligibility check failed.")
    if not summary["packaging_assets_present"]:
        raise RuntimeError("One or more Windows packaging assets are missing.")

    sections_2d, include_plotlyjs = _figure_html(
        preview_2d,
        include_plotlyjs="inline",
    )
    sections_3d, _ = _figure_html(
        preview_3d,
        include_plotlyjs=include_plotlyjs,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        output_directory / "phase5_validation_summary.json",
        summary,
        overwrite=True,
    )
    write_text_atomic(
        output_directory / "phase5_validation.html",
        _report_html(summary, sections_2d + sections_3d),
        overwrite=True,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
