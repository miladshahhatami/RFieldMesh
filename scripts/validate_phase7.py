"""Validate stable-release metadata, documentation, and built distributions."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(check_id: str, passed: bool, details: str) -> dict[str, object]:
    return {"check_id": check_id, "passed": passed, "details": details}


def _citation_version(content: str) -> str | None:
    match = re.search(r"^version:\s*([^\s]+)\s*$", content, flags=re.MULTILINE)
    return match.group(1) if match else None


def _report(summary: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item['check_id']))}</td>"
        f'<td class="{"pass" if item["passed"] else "fail"}">'
        f"{'passed' if item['passed'] else 'failed'}</td>"
        f"<td>{html.escape(str(item['details']))}</td>"
        "</tr>"
        for item in summary["checks"]
    )
    artifact_rows = "".join(
        f"<li><code>{html.escape(name)}</code>: <code>{checksum}</code></li>"
        for name, checksum in summary["artifacts"].items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RFieldMesh 1.0.0 Phase 7 validation</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 28px; color: #1f2933; }}
h1 {{ color: #173f5f; }}
table {{ border-collapse: collapse; width: 100%; max-width: 1100px; }}
th, td {{ border: 1px solid #d9e2ec; padding: 9px 11px; text-align: left; }}
th {{ background: #f0f4f8; }}
.pass {{ color: #147d64; font-weight: 700; }}
.fail {{ color: #b42318; font-weight: 700; }}
code {{ background: #f0f4f8; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>RFieldMesh 1.0.0 — Phase 7 validation</h1>
<p>Stable source release ready:
<strong>{str(summary["source_release_ready"]).lower()}</strong></p>
<p>Native Phase 6 status:
<strong>{html.escape(str(summary["native_validation_status"]))}</strong></p>
<table>
<thead><tr><th>Check</th><th>Status</th><th>Details</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<h2>Built-artifact checksums</h2>
<ul>{artifact_rows}</ul>
<p>External GitHub, PyPI, and DOI publication was not performed by this
source-validation run.</p>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-directory", type=Path, default=Path("dist-phase7"))
    parser.add_argument("--output-directory", type=Path, default=Path("validation/output"))
    arguments = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(pyproject["project"]["version"])
    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    limitations = (root / "KNOWN_LIMITATIONS.md").read_text(encoding="utf-8")
    promotion = json.loads(
        (root / "validation/stable_release/promotion_record.json").read_text(encoding="utf-8")
    )

    required_documents = (
        "README.md",
        "KNOWN_LIMITATIONS.md",
        "RELEASE_NOTES_1.0.0.md",
        "CITATION.cff",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "docs/user_guide/quickstart.md",
        "docs/release/publication_checklist.md",
        "docs/publication/manuscript_limitations.md",
    )
    missing = [path for path in required_documents if not (root / path).is_file()]
    checks = [
        _check("stable_version", version == "1.0.0", f"pyproject version is {version}."),
        _check(
            "citation_version",
            _citation_version(citation) == version,
            f"CITATION.cff version is {_citation_version(citation)!r}.",
        ),
        _check(
            "changelog_entry",
            "## 1.0.0 — Stable release" in changelog,
            "The stable changelog entry is present.",
        ),
        _check(
            "documentation_inventory",
            not missing,
            "All required stable documents are present."
            if not missing
            else f"Missing: {', '.join(missing)}",
        ),
        _check(
            "large_mesh_disclosure",
            all(
                term in (readme + limitations).lower()
                for term in ("dense", "karhunen", "axis-aligned", "rotated", "unstructured")
            ),
            "Dense KL and structured spectral applicability limits are disclosed.",
        ),
        _check(
            "promotion_provenance",
            promotion.get("promotion_source_version") == "0.9.0rc1"
            and promotion.get("scientific_core_changed_during_promotion") is False,
            "Promotion source and scientific-core freeze are recorded.",
        ),
        _check(
            "native_attestation_label",
            promotion.get("native_validation", {}).get("status") == "user_attested"
            and promotion.get("native_validation", {}).get("machine_evidence_uploaded") is False,
            "Native validation is labelled as user attestation, not machine evidence.",
        ),
    ]

    dist_directory = (root / arguments.dist_directory).resolve()
    expected_wheel = dist_directory / f"rfieldmesh-{version}-py3-none-any.whl"
    expected_sdist = dist_directory / f"rfieldmesh-{version}.tar.gz"
    checks.extend(
        (
            _check(
                "wheel_built",
                expected_wheel.is_file(),
                f"Expected wheel: {expected_wheel.name}.",
            ),
            _check(
                "source_distribution_built",
                expected_sdist.is_file(),
                f"Expected source distribution: {expected_sdist.name}.",
            ),
        )
    )

    artifacts = {
        path.name: _sha256(path) for path in (expected_wheel, expected_sdist) if path.is_file()
    }
    ready = all(bool(item["passed"]) for item in checks)
    summary: dict[str, Any] = {
        "application_version": version,
        "artifacts": artifacts,
        "checks": checks,
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "external_publication": {
            "github": "not_performed",
            "pypi": "not_performed",
            "zenodo": "not_performed",
        },
        "native_validation_status": "user_attested_phase6_completion",
        "schema_version": "1.0",
        "source_release_ready": ready,
    }

    output_directory = (root / arguments.output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    summary_path = output_directory / "phase7_validation_summary.json"
    report_path = output_directory / "phase7_validation.html"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_report(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
