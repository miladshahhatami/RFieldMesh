"""Prepare and record Phase 6 scientific and native-validation fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rfieldmesh import __version__
from rfieldmesh.application.generate import generate_model
from rfieldmesh.config.models import GenerationConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    details: str,
) -> None:
    checks.append({"check_id": check_id, "passed": passed, "details": details})
    if not passed:
        raise RuntimeError(details)


def _small_config(project_root: Path) -> GenerationConfig:
    project = project_root / "validation" / "abaqus" / "small_explicit_generation.json"
    raw = json.loads(project.read_text(encoding="utf-8"))
    directory = project.parent
    raw["source_path"] = str((directory / raw["source_path"]).resolve())
    raw["output_path"] = str((directory / raw["output_path"]).resolve())
    return GenerationConfig.model_validate(raw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-2d", type=Path, required=True)
    parser.add_argument("--model-3d", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("validation/release_candidate/evidence/scientific_validation.json"),
    )
    arguments = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = (project_root / arguments.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    artifacts: dict[str, str] = {}
    notes: list[str] = []
    status = "failed"
    try:
        phase5_log = output.parent / "phase5-regression.log"
        phase5_command = [
            sys.executable,
            str(project_root / "scripts" / "validate_phase5.py"),
            "--model-2d",
            str(arguments.model_2d.expanduser().resolve()),
            "--model-3d",
            str(arguments.model_3d.expanduser().resolve()),
            "--output-directory",
            str(project_root / "validation" / "output"),
        ]
        completed = subprocess.run(
            phase5_command,
            check=False,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        phase5_log.write_text(completed.stdout, encoding="utf-8")
        _check(
            checks,
            "phase5_scientific_regression",
            completed.returncode == 0,
            f"Phase 5 supplied-model regression exited with code {completed.returncode}.",
        )
        summary_path = project_root / "validation" / "output" / "phase5_validation_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        _check(
            checks,
            "supplied_2d_model",
            summary["preview_2d"]["eligible_count"] == 20_000,
            "The private 2D case resolved exactly 20,000 eligible elements.",
        )
        _check(
            checks,
            "supplied_3d_model",
            summary["preview_3d"]["eligible_count"] == 108
            and summary["preview_3d"]["selected_count"] == 138
            and summary["preview_3d"]["excluded_by_type"] == {"AC3D8R": 30},
            "The private mixed 3D case resolved 108 C3D8R and excluded 30 AC3D8R elements.",
        )

        generated = generate_model(_small_config(project_root))
        _check(
            checks,
            "redistributable_explicit_fixture",
            generated.validation.valid and generated.validation.checked_elements == 2,
            "The two-element Abaqus/Explicit fixture generated and reparsed successfully.",
        )
        manifest = json.loads(generated.manifest_path.read_text(encoding="utf-8"))
        _check(
            checks,
            "native_assignment_provenance",
            len(manifest["assignment"]["material_names_by_element"]) == 2
            and len(manifest["assignment"]["set_names_by_element"]) == 2,
            "The manifest records exact generated material and element-set names.",
        )
        generated_text = generated.assignment.output_path.read_text(encoding="utf-8")
        _check(
            checks,
            "material_card_preservation",
            generated_text.casefold().count("*damping") == 3,
            "The source damping card is retained in the original and both cloned materials.",
        )

        required_assets = (
            project_root / "packaging" / "abaqus" / "validate_generated_model.py",
            project_root / "packaging" / "abaqus" / "validate.ps1",
            project_root / "packaging" / "windows" / "write_evidence.py",
            project_root / "packaging" / "windows" / "clean_machine_test.ps1",
            project_root / "packaging" / "licences" / "LGPL-3.0.txt",
            project_root / "packaging" / "licences" / "GPL-3.0.txt",
            project_root / "docs" / "release" / "phase6_user_acceptance.md",
        )
        _check(
            checks,
            "native_release_assets",
            all(path.is_file() and path.stat().st_size > 0 for path in required_assets),
            "Windows, Abaqus, acceptance, and complete Qt licence assets are present.",
        )
        for path in (
            summary_path,
            project_root / "validation" / "output" / "phase5_validation.html",
            generated.assignment.output_path,
            generated.manifest_path,
            phase5_log,
        ):
            artifacts[path.name] = _sha256(path)
        status = "passed"
    except Exception as exc:
        checks.append(
            {
                "check_id": "scientific_validation_exception",
                "passed": False,
                "details": f"{type(exc).__name__}: {exc}",
            }
        )
        notes.append(traceback.format_exc())

    report = {
        "schema_version": "1.0",
        "gate_id": "scientific_validation",
        "status": status,
        "application_version": __version__,
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "checks": checks,
        "artifacts": artifacts,
        "notes": notes,
    }
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if status != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
