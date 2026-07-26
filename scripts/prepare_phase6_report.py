"""Create the Phase 6 release-gate audit and human-readable status report."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from rfieldmesh.infrastructure.atomic_files import write_json_atomic, write_text_atomic
from rfieldmesh.release.evidence import audit_release_evidence, evidence_paths


def _report(audit: dict[str, object]) -> str:
    rows = []
    for gate in audit["gates"]:  # type: ignore[union-attr]
        status = gate["status"]  # type: ignore[index]
        status_class = "pass" if status == "passed" else "pending"
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(gate['gate_id']))}</td>"  # type: ignore[index]
            f'<td class="{status_class}">{html.escape(str(status))}</td>'
            f"<td>{html.escape(str(gate['reason']))}</td>"  # type: ignore[index]
            "</tr>"
        )
    ready = bool(audit["candidate_ready"])
    outcome = (
        "All mandatory release gates passed."
        if ready
        else "Release approval is withheld until every native and acceptance gate passes."
    )
    outcome_class = "pass" if ready else "pending"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RFieldMesh Phase 6 release audit</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 28px; color: #1f2933; }}
h1 {{ color: #173f5f; }}
table {{ border-collapse: collapse; width: 100%; max-width: 1050px; }}
th, td {{ border: 1px solid #d9e2ec; padding: 9px 11px; text-align: left; }}
th {{ background: #f0f4f8; }}
.pass {{ color: #147d64; font-weight: 700; }}
.pending {{ color: #9c5d10; font-weight: 700; }}
code {{ background: #f0f4f8; padding: 2px 4px; }}
</style>
</head>
<body>
<h1>RFieldMesh Phase 6 release audit</h1>
<p>Candidate version: <code>{html.escape(str(audit["application_version"]))}</code></p>
<p class="{outcome_class}">{html.escape(outcome)}</p>
<table>
<thead><tr><th>Gate</th><th>Status</th><th>Decision basis</th></tr></thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
<p>Missing evidence is a pending release condition, not a test success.</p>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-directory",
        type=Path,
        default=Path("validation/release_candidate/evidence"),
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("validation/output"),
    )
    arguments = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    evidence_directory = (project_root / arguments.evidence_directory).resolve()
    output_directory = (project_root / arguments.output_directory).resolve()
    evidence_directory.mkdir(parents=True, exist_ok=True)
    output_directory.mkdir(parents=True, exist_ok=True)
    audit = audit_release_evidence(evidence_paths(evidence_directory))
    content = audit.as_dict()
    write_json_atomic(
        output_directory / "phase6_validation_summary.json",
        content,
        overwrite=True,
    )
    write_text_atomic(
        output_directory / "phase6_validation.html",
        _report(content),
        overwrite=True,
    )
    print(json.dumps(content, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
