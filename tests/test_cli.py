"""Command-line workflow smoke tests."""

import json
from pathlib import Path

from typer.testing import CliRunner

from rfieldmesh.cli.app import app

runner = CliRunner()


def test_inspect_command_emits_json(small_inp: Path) -> None:
    result = runner.invoke(app, ["inspect", str(small_inp)])
    assert result.exit_code == 0
    summary = json.loads(result.stdout)
    assert summary["parts"][0]["name"] == "Soil Part"


def test_generate_command_resolves_paths_relative_to_project(
    small_inp: Path,
) -> None:
    project = small_inp.parent / "project.json"
    project.write_text(
        json.dumps(
            {
                "source_path": small_inp.name,
                "output_path": "cli_generated.inp",
                "part_name": "Soil Part",
                "set_name": "Target",
                "variables": [
                    {
                        "property_kind": "youngs_modulus",
                        "moments": {
                            "mean": 20000000.0,
                            "standard_deviation": 4000000.0,
                        },
                        "distribution": "lognormal",
                        "correlation": {
                            "model": "exponential",
                            "scales": [2.0, 1.0],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["generate", str(project)])
    assert result.exit_code == 0
    assert (small_inp.parent / "cli_generated.inp").exists()
    assert (small_inp.parent / "cli_generated.rfieldmesh.json").exists()
    assert "Validated elements: 2" in result.stdout


def test_preview_command_writes_offline_html(small_inp: Path) -> None:
    project = small_inp.parent / "preview_project.json"
    project.write_text(
        json.dumps(
            {
                "source_path": small_inp.name,
                "output_path": "unused.inp",
                "part_name": "Soil Part",
                "set_name": "Target",
                "variables": [
                    {
                        "property_kind": "youngs_modulus",
                        "moments": {
                            "mean": 20000000.0,
                            "standard_deviation": 4000000.0,
                        },
                        "distribution": "lognormal",
                        "correlation": {
                            "model": "exponential",
                            "scales": [2.0, 1.0],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = small_inp.parent / "cli_preview.html"
    result = runner.invoke(
        app,
        ["preview", str(project), "--output", str(output)],
    )
    assert result.exit_code == 0
    assert output.exists()
    assert "Eligible elements: 2" in result.stdout


def test_batch_command_resolves_nested_generation_paths(small_inp: Path) -> None:
    project = small_inp.parent / "batch_project.json"
    project.write_text(
        json.dumps(
            {
                "generation": {
                    "source_path": small_inp.name,
                    "output_path": "ignored.inp",
                    "part_name": "Soil Part",
                    "set_name": "Target",
                    "variables": [
                        {
                            "property_kind": "youngs_modulus",
                            "moments": {
                                "mean": 20000000.0,
                                "standard_deviation": 4000000.0,
                            },
                            "distribution": "lognormal",
                            "correlation": {
                                "model": "exponential",
                                "scales": [2.0, 1.0],
                            },
                        }
                    ],
                },
                "output_directory": "cli_batch",
                "realization_count": 2,
                "filename_template": "case_{index}.inp",
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["batch", str(project)])
    assert result.exit_code == 0
    assert (small_inp.parent / "cli_batch" / "case_0.inp").exists()
    assert (small_inp.parent / "cli_batch" / "case_1.inp").exists()
    assert "Generated realizations: 2" in result.stdout


def test_release_audit_fails_closed_when_native_evidence_is_missing(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        ["release-audit", str(tmp_path), "--require-ready"],
    )
    assert result.exit_code == 1
    assert '"candidate_ready": false' in result.stdout
    assert "Candidate ready: false" in result.stdout
