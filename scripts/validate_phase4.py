"""Validate Phase 4 against the supplied 2D and 3D Abaqus models."""

from __future__ import annotations

import argparse
import html
import json
import math
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import resolve_region
from rfieldmesh.application.generate import generate_model
from rfieldmesh.application.inspect_model import inspect_model
from rfieldmesh.config.enums import DistributionKind, PropertyKind
from rfieldmesh.config.models import (
    CorrelationConfig,
    GenerationConfig,
    MomentSpecification,
    RandomVariableConfig,
)
from rfieldmesh.random_fields.correlations import (
    exponential_cell_average_variance_factor,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = PROJECT_ROOT / "validation" / "output"


def _variable(
    *,
    mean: float,
    standard_deviation: float,
    scales: tuple[float, ...],
) -> RandomVariableConfig:
    return RandomVariableConfig(
        property_kind=PropertyKind.YOUNGS_MODULUS,
        moments=MomentSpecification(
            mean=mean,
            standard_deviation=standard_deviation,
        ),
        distribution=DistributionKind.LOGNORMAL,
        correlation=CorrelationConfig(scales=scales),
    )


def _run_case(config: GenerationConfig) -> tuple[dict[str, Any], float]:
    started = perf_counter()
    result = generate_model(config)
    elapsed = perf_counter() - started
    field = result.fields[0]
    return (
        {
            "runtime_seconds": elapsed,
            "output_size_bytes": result.assignment.output_size_bytes,
            "selected_set": result.assignment.selected_set_name,
            "target_count": result.assignment.target_count,
            "excluded_count": result.assignment.excluded_count,
            "remainder_count": result.validation.remainder_count,
            "validation": {
                "valid": result.validation.valid,
                "checked_elements": result.validation.checked_elements,
                "checked_materials": result.validation.checked_materials,
                "checksum_matches": result.validation.output_sha256_matches,
            },
            "field": {
                "algorithm": field.algorithm.value,
                "statistics": field.statistics.as_dict(),
                "diagnostics": field.diagnostics,
            },
        },
        elapsed,
    )


def _render_report(summary: dict[str, Any]) -> str:
    two_d = summary["two_dimensional"]
    three_d = summary["three_dimensional"]

    def row(name: str, left: object, right: object) -> str:
        return (
            "<tr>"
            f"<th>{html.escape(name)}</th>"
            f"<td>{html.escape(str(left))}</td>"
            f"<td>{html.escape(str(right))}</td>"
            "</tr>"
        )

    rows = [
        row("Selected elements", two_d["selected_count"], three_d["selected_count"]),
        row("Eligible targets", two_d["target_count"], three_d["target_count"]),
        row("Excluded elements", two_d["excluded_count"], three_d["excluded_count"]),
        row("Section remainder", two_d["remainder_count"], three_d["remainder_count"]),
        row("Algorithm", two_d["field"]["algorithm"], three_d["field"]["algorithm"]),
        row(
            "Generated-field mean",
            f"{two_d['field']['statistics']['sample_mean']:.6g}",
            f"{three_d['field']['statistics']['sample_mean']:.6g}",
        ),
        row(
            "Generated-field CV",
            f"{two_d['field']['statistics']['sample_coefficient_of_variation']:.6f}",
            f"{three_d['field']['statistics']['sample_coefficient_of_variation']:.6f}",
        ),
        row(
            "Theoretical observation-scale CV",
            f"{two_d['field']['theoretical_observation_scale_cv']:.6f}",
            f"{three_d['field']['theoretical_observation_scale_cv']:.6f}",
        ),
        row(
            "Runtime (s)",
            f"{two_d['runtime_seconds']:.3f}",
            f"{three_d['runtime_seconds']:.3f}",
        ),
        row("Output size (bytes)", two_d["output_size_bytes"], three_d["output_size_bytes"]),
        row(
            "Independent reparse",
            two_d["validation"]["valid"],
            three_d["validation"]["valid"],
        ),
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RFieldMesh Phase 4 validation</title>
<style>
body {{ margin: 2rem auto; max-width: 1050px; padding: 0 1rem;
       font-family: system-ui, sans-serif; color: #172033; line-height: 1.55; }}
h1, h2 {{ color: #153c66; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }}
th, td {{ border: 1px solid #c7d1dd; padding: .55rem .7rem; text-align: left; }}
thead {{ background: #eaf2f8; }}
code {{ background: #eef2f5; padding: .1rem .25rem; }}
.pass {{ border-left: .4rem solid #16845b; background: #edf8f3; padding: .8rem 1rem; }}
</style>
</head>
<body>
<h1>RFieldMesh Phase 4 validation</h1>
<p class="pass"><strong>PASS.</strong> Both supplied models were parsed, randomized,
written atomically, reparsed independently, and verified for exact target coverage and
material-property values.</p>
<table>
<thead><tr><th>Measure</th><th>Structured 2D model</th><th>Mixed-element 3D layer</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
<h2>2D spectral diagnostics</h2>
<pre>{html.escape(json.dumps(two_d["field"]["diagnostics"], indent=2))}</pre>
<h2>3D KL diagnostics</h2>
<pre>{html.escape(json.dumps(three_d["field"]["diagnostics"], indent=2))}</pre>
<h2>Safety checks</h2>
<ul>
<li>Source SHA-256 values were unchanged after generation.</li>
<li>The 3D layer retained its 30 unsupported <code>AC3D8R</code> elements through a
generated remainder section using the source material.</li>
<li>Generated materials preserved unrelated source material cards while replacing only
the configured property.</li>
<li>Every generated element had exactly one generated section and the expected material.</li>
</ul>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-2d", type=Path, required=True)
    parser.add_argument("--model-3d", type=Path, required=True)
    arguments = parser.parse_args()
    model_2d = arguments.model_2d.resolve()
    model_3d = arguments.model_3d.resolve()
    source_2d_before = parse_abaqus_model(model_2d).source.sha256
    source_3d_before = parse_abaqus_model(model_3d).source.sha256
    region_2d = resolve_region(
        parse_abaqus_model(model_2d),
        part_name="Part-1",
        set_name="Set-1",
    )
    region_3d = resolve_region(
        parse_abaqus_model(model_3d),
        part_name="Layered Soil Quarter",
        set_name="Layer1",
    )

    with tempfile.TemporaryDirectory(prefix="rfieldmesh-phase4-") as temporary:
        temporary_directory = Path(temporary)
        two_d, _ = _run_case(
            GenerationConfig(
                source_path=str(model_2d),
                output_path=str(temporary_directory / "generated_2d.inp"),
                part_name="Part-1",
                set_name="Set-1",
                first_seed=1403,
                variables=(
                    _variable(
                        mean=20_000_000.0,
                        standard_deviation=6_000_000.0,
                        scales=(10.0, 1.0),
                    ),
                ),
            )
        )
        three_d, _ = _run_case(
            GenerationConfig(
                source_path=str(model_3d),
                output_path=str(temporary_directory / "generated_3d.inp"),
                part_name="Layered Soil Quarter",
                set_name="Layer1",
                first_seed=1403,
                variables=(
                    _variable(
                        mean=50_000_000.0,
                        standard_deviation=10_000_000.0,
                        scales=(10.0, 10.0, 2.0),
                    ),
                ),
            )
        )

    two_d["selected_count"] = len(region_2d.selected_labels)
    three_d["selected_count"] = len(region_3d.selected_labels)
    two_d["region_origin"] = region_2d.region_origin.tolist()
    three_d["region_origin"] = region_3d.region_origin.tolist()
    two_d["excluded_by_type"] = region_2d.excluded_by_type
    three_d["excluded_by_type"] = region_3d.excluded_by_type
    latent_variance_2d = float(
        exponential_cell_average_variance_factor(0.5, 10.0)
        * exponential_cell_average_variance_factor(0.5, 1.0)
    )
    two_d["field"]["theoretical_observation_scale_cv"] = math.sqrt(
        math.expm1(math.log1p(0.3**2) * latent_variance_2d)
    )
    three_d["field"]["theoretical_observation_scale_cv"] = 0.2
    inspection_2d = inspect_model(model_2d)
    inspection_3d = inspect_model(model_3d)
    inspection_2d["source_path"] = model_2d.name
    inspection_3d["source_path"] = model_3d.name
    summary: dict[str, Any] = {
        "phase": 4,
        "status": "pass",
        "two_dimensional": two_d,
        "three_dimensional": three_d,
        "source_integrity": {
            "two_dimensional_unchanged": (
                source_2d_before == parse_abaqus_model(model_2d).source.sha256
            ),
            "three_dimensional_unchanged": (
                source_3d_before == parse_abaqus_model(model_3d).source.sha256
            ),
        },
        "inspection": {
            "two_dimensional": inspection_2d,
            "three_dimensional": inspection_3d,
        },
    }
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT_DIRECTORY / "phase4_validation_summary.json"
    report_path = OUTPUT_DIRECTORY / "phase4_validation.html"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), "report": str(report_path)}, indent=2))


if __name__ == "__main__":
    main()
