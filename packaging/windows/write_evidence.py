"""Create the machine-readable native Windows release-gate evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(checks: list[dict[str, Any]], check_id: str, passed: bool, details: str) -> None:
    checks.append({"check_id": check_id, "passed": passed, "details": details})


def build_evidence(
    *,
    source_report: Path,
    packaged_report: Path,
    executable: Path,
    licence_inventory: Path,
    third_party_notice: Path,
    gpl_text: Path,
    lgpl_text: Path,
) -> dict[str, Any]:
    """Validate smoke reports and return one release-evidence document."""
    source = _load(source_report)
    packaged = _load(packaged_report)
    checks: list[dict[str, Any]] = []
    _check(
        checks,
        "source_quality_gates",
        True,
        "Tests, linting, formatting, typing, and package build completed before packaging.",
    )
    _check(
        checks,
        "source_gui_smoke",
        source.get("tab_count") == 5 and source.get("frozen") is False,
        "Source GUI constructed five tabs and exited through the timed smoke path.",
    )
    _check(
        checks,
        "packaged_gui_smoke",
        packaged.get("tab_count") == 5 and packaged.get("frozen") is True,
        "Frozen GUI constructed five tabs and exited normally without an external Python process.",
    )
    _check(
        checks,
        "version_identity",
        source.get("application_version") == packaged.get("application_version"),
        "Source and frozen application versions are identical.",
    )
    _check(
        checks,
        "licence_inventory",
        licence_inventory.is_file()
        and licence_inventory.stat().st_size > 0
        and third_party_notice.is_file()
        and third_party_notice.stat().st_size > 0,
        "Dependency inventory and third-party notices are present in the distribution.",
    )
    _check(
        checks,
        "complete_qt_licences",
        gpl_text.is_file()
        and gpl_text.stat().st_size > 30_000
        and lgpl_text.is_file()
        and lgpl_text.stat().st_size > 7_000,
        "Complete GPL-3.0 and LGPL-3.0 texts are present in the distribution.",
    )
    _check(
        checks,
        "windows_executable",
        executable.is_file() and executable.stat().st_size > 0,
        "The PyInstaller one-folder executable is present.",
    )
    status = "passed" if all(item["passed"] for item in checks) else "failed"
    artifacts = {}
    for name, path in (
        ("RFieldMesh.exe", executable),
        ("PYTHON_PACKAGE_LICENCES.txt", licence_inventory),
        ("THIRD_PARTY_NOTICES.md", third_party_notice),
        ("GPL-3.0.txt", gpl_text),
        ("LGPL-3.0.txt", lgpl_text),
    ):
        if path.is_file():
            artifacts[name] = _sha256(path)
    return {
        "schema_version": "1.0",
        "gate_id": "windows_build",
        "status": status,
        "application_version": str(packaged.get("application_version", "unknown")),
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "qt_version": packaged.get("qt_version"),
            "pyside_version": packaged.get("pyside_version"),
        },
        "checks": checks,
        "artifacts": artifacts,
        "notes": (),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--packaged-report", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--licence-inventory", type=Path, required=True)
    parser.add_argument("--third-party-notice", type=Path, required=True)
    parser.add_argument("--gpl-text", type=Path, required=True)
    parser.add_argument("--lgpl-text", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    evidence = build_evidence(
        source_report=arguments.source_report.resolve(),
        packaged_report=arguments.packaged_report.resolve(),
        executable=arguments.executable.resolve(),
        licence_inventory=arguments.licence_inventory.resolve(),
        third_party_notice=arguments.third_party_notice.resolve(),
        gpl_text=arguments.gpl_text.resolve(),
        lgpl_text=arguments.lgpl_text.resolve(),
    )
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    if evidence["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
