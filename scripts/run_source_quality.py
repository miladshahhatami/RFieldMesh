"""Run and record the complete platform-independent release-quality gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rfieldmesh import __version__


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(
    *,
    check_id: str,
    description: str,
    command: list[str],
    log_path: Path,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_path.write_text(completed.stdout, encoding="utf-8")
    return {
        "check_id": check_id,
        "passed": completed.returncode == 0,
        "details": (
            f"{description}; exit code {completed.returncode}. Complete output: {log_path.name}"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("validation/stable_release/source_quality.json"),
    )
    parser.add_argument(
        "--distribution-directory",
        type=Path,
        default=Path("dist-phase7"),
    )
    arguments = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = (project_root / arguments.output).resolve()
    distribution_directory = (project_root / arguments.distribution_directory).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    distribution_directory.mkdir(parents=True, exist_ok=True)

    coverage = output.parent / "source-coverage.json"
    junit = output.parent / "source-pytest-junit.xml"
    commands = (
        (
            "pytest",
            "Automated tests and coverage",
            [
                sys.executable,
                "-m",
                "pytest",
                "--junitxml",
                str(junit),
                "--cov=rfieldmesh",
                "--cov-report=term-missing",
                f"--cov-report=json:{coverage}",
            ],
        ),
        ("ruff_lint", "Ruff lint check", [sys.executable, "-m", "ruff", "check", "."]),
        (
            "ruff_format",
            "Ruff format check",
            [sys.executable, "-m", "ruff", "format", "--check", "."],
        ),
        ("mypy", "Strict mypy check", [sys.executable, "-m", "mypy", "src"]),
        (
            "package_build",
            "Wheel and source-distribution build",
            [
                sys.executable,
                "-m",
                "build",
                "--outdir",
                str(distribution_directory),
            ],
        ),
    )
    checks = [
        _run(
            check_id=check_id,
            description=description,
            command=command,
            log_path=output.parent / f"source-{check_id}.log",
        )
        for check_id, description, command in commands
    ]
    artifacts = {
        path.name: _sha256(path)
        for path in sorted(
            (
                *distribution_directory.glob("*.whl"),
                *distribution_directory.glob("*.tar.gz"),
                coverage,
                junit,
            ),
            key=lambda item: item.name,
        )
        if path.is_file()
    }
    report = {
        "schema_version": "1.0",
        "gate_id": "source_quality",
        "status": "passed" if all(check["passed"] for check in checks) else "failed",
        "application_version": __version__,
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "checks": checks,
        "artifacts": artifacts,
        "notes": (),
    }
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
