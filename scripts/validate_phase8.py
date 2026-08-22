"""Validate Phase 8 publication preparation without claiming external release."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
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
<title>RFieldMesh 1.0.0 Phase 8 validation</title>
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
<h1>RFieldMesh 1.0.0 — Phase 8 publication preparation</h1>
<p>Publication-preparation bundle ready:
<strong>{str(summary["preparation_ready"]).lower()}</strong></p>
<p>External publication status:
<strong>{html.escape(str(summary["external_publication_status"]))}</strong></p>
<table>
<thead><tr><th>Check</th><th>Status</th><th>Details</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<h2>Release-artifact checksums</h2>
<ul>{artifact_rows}</ul>
<p>This report does not claim that GitHub, Zenodo, or the stable Windows
archive exists. Those actions require maintainer-owned accounts or a native
Windows build from the exact tagged source.</p>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-directory", type=Path, default=Path("dist-phase8"))
    parser.add_argument("--output-directory", type=Path, default=Path("validation/output"))
    arguments = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    dist_directory = (root / arguments.dist_directory).resolve()
    required_files = (
        ".zenodo.json",
        "CITATION.cff",
        "docs/assets/rfieldmesh-social-preview.png",
        "docs/publication/HIGHLIGHTS.txt",
        "docs/publication/RFieldMesh_SoftwareX_Manuscript_v1.0.0.docx",
        "docs/publication/manuscript/rfieldmesh-graphical-abstract.png",
        "docs/publication/softwarex_manuscript.md",
        "docs/release/phase8_publication.md",
    )
    missing = [path for path in required_files if not (root / path).is_file()]
    expected_artifacts = (
        dist_directory / "rfieldmesh-1.0.0-py3-none-any.whl",
        dist_directory / "rfieldmesh-1.0.0.tar.gz",
    )
    manuscript = (root / "docs/publication/softwarex_manuscript.md").read_text(encoding="utf-8")
    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    checks = [
        _check(
            "publication_inventory",
            not missing,
            "All Phase 8 publication files are present."
            if not missing
            else f"Missing: {', '.join(missing)}",
        ),
        _check(
            "distribution_inventory",
            all(path.is_file() for path in expected_artifacts),
            "The wheel and source distribution are present.",
        ),
        _check(
            "limitation_disclosure",
            all(term in manuscript.lower() for term in ("rotated", "skewed", "unstructured")),
            "The large general-mesh limitation is disclosed in the manuscript.",
        ),
        _check(
            "external_identifier_safety",
            "doi:" not in citation.lower() and "github.com/" not in citation.lower(),
            "No repository URL or DOI was invented before external publication.",
        ),
        _check(
            "stable_windows_provenance",
            all(
                term in manuscript.lower()
                for term in ("0.9.0rc1", "stable source", "windows archive")
            ),
            "The tested release candidate is distinguished from the pending stable binary.",
        ),
    ]
    artifacts = {path.name: _sha256(path) for path in expected_artifacts if path.is_file()}
    ready = all(bool(item["passed"]) for item in checks)
    summary: dict[str, Any] = {
        "application_version": "1.0.0",
        "artifacts": artifacts,
        "checks": checks,
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "external_publication": {
            "github": "pending_maintainer_authorization",
            "stable_windows_archive": "pending_native_build_or_upload",
            "zenodo": "pending_public_github_release",
        },
        "external_publication_status": "pending maintainer-authorized actions",
        "preparation_ready": ready,
        "schema_version": "1.0",
    }

    output_directory = (root / arguments.output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    summary_path = output_directory / "phase8_validation_summary.json"
    report_path = output_directory / "phase8_validation.html"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_report(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
