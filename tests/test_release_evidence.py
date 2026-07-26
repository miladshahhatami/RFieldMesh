"""Fail-closed release-evidence contract tests."""

import json
from pathlib import Path

from rfieldmesh import __version__
from rfieldmesh.release.evidence import (
    REQUIRED_RELEASE_GATES,
    GateEvidence,
    audit_release_evidence,
    load_gate_evidence,
)


def _content(gate_id: str, *, version: str = __version__) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "gate_id": gate_id,
        "status": "passed",
        "application_version": version,
        "executed_at_utc": "2026-07-25T12:00:00+00:00",
        "environment": {"platform": "test"},
        "checks": [
            {
                "check_id": "acceptance",
                "passed": True,
                "details": "The test gate passed.",
            }
        ],
        "artifacts": {"artifact.bin": "a" * 64},
        "notes": [],
    }


def _write(directory: Path, gate_id: str, *, version: str = __version__) -> Path:
    path = directory / f"{gate_id}.json"
    path.write_text(json.dumps(_content(gate_id, version=version)), encoding="utf-8")
    return path


def test_evidence_contract_rejects_pass_with_failed_check() -> None:
    content = _content("source_quality")
    content["checks"] = [{"check_id": "tests", "passed": False, "details": "One test failed."}]
    try:
        GateEvidence.model_validate(content)
    except ValueError as exc:
        assert "Passed release evidence" in str(exc)
    else:  # pragma: no cover - defensive failure message
        raise AssertionError("Inconsistent passing evidence was accepted.")


def test_all_required_matching_reports_approve_candidate(tmp_path: Path) -> None:
    paths = [_write(tmp_path, gate_id) for gate_id in REQUIRED_RELEASE_GATES]
    assert load_gate_evidence(paths[0]).status == "passed"
    audit = audit_release_evidence(paths)
    assert audit.candidate_ready
    assert all(gate.status == "passed" for gate in audit.gates)


def test_missing_and_stale_evidence_cannot_approve_candidate(tmp_path: Path) -> None:
    stale = _write(tmp_path, "source_quality", version="0.3.0a1")
    audit = audit_release_evidence([stale])
    assert not audit.candidate_ready
    assert audit.gates[0].status == "invalid"
    assert any(gate.status == "missing" for gate in audit.gates[1:])


def test_duplicate_evidence_is_invalid(tmp_path: Path) -> None:
    first = _write(tmp_path, "source_quality")
    duplicate_directory = tmp_path / "duplicate"
    duplicate_directory.mkdir()
    second = _write(duplicate_directory, "source_quality")
    audit = audit_release_evidence([first, second])
    assert audit.gates[0].status == "invalid"
    assert not audit.candidate_ready
