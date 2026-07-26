"""Machine-readable evidence contracts for native release gates."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rfieldmesh import __version__

EvidenceStatus = Literal["passed", "failed", "not_run"]

REQUIRED_RELEASE_GATES: tuple[str, ...] = (
    "source_quality",
    "scientific_validation",
    "windows_build",
    "windows_clean_machine",
    "abaqus_import_2d",
    "abaqus_import_3d",
    "abaqus_explicit_analysis",
    "user_acceptance",
)


class EvidenceCheck(BaseModel):
    """One independently inspectable assertion within a release gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str = Field(min_length=1, max_length=100)
    passed: bool
    details: str = Field(min_length=1)


class GateEvidence(BaseModel):
    """Versioned evidence supplied by one release-gate execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    gate_id: str = Field(min_length=1, max_length=100)
    status: EvidenceStatus
    application_version: str = Field(min_length=1)
    executed_at_utc: datetime
    environment: dict[str, Any]
    checks: tuple[EvidenceCheck, ...]
    artifacts: dict[str, str] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @field_validator("executed_at_utc")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject timestamps that cannot prove their UTC relationship."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Release evidence timestamps must include a UTC offset.")
        return value

    @field_validator("artifacts")
    @classmethod
    def validate_artifact_hashes(cls, values: dict[str, str]) -> dict[str, str]:
        """Require lowercase SHA-256 values for every recorded artifact."""
        for name, checksum in values.items():
            if not name:
                raise ValueError("Evidence artifact names must not be empty.")
            if len(checksum) != 64 or any(
                character not in "0123456789abcdef" for character in checksum
            ):
                raise ValueError(f"Artifact {name!r} does not have a lowercase SHA-256 value.")
        return values

    @model_validator(mode="after")
    def status_matches_checks(self) -> GateEvidence:
        """Make a passed status impossible when a constituent check failed."""
        if self.status == "passed" and (
            not self.checks or not all(item.passed for item in self.checks)
        ):
            raise ValueError(
                "Passed release evidence requires at least one passing check and no failures."
            )
        if self.status == "failed" and self.checks and all(item.passed for item in self.checks):
            raise ValueError("Failed release evidence must contain at least one failed check.")
        return self


class GateAudit(BaseModel):
    """Normalized outcome for one required gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_id: str
    status: Literal["passed", "failed", "not_run", "missing", "invalid"]
    evidence_path: str | None = None
    reason: str


class ReleaseAudit(BaseModel):
    """Aggregate decision over all mandatory native release evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    application_version: str
    candidate_ready: bool
    gates: tuple[GateAudit, ...]
    ignored_files: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""
        return self.model_dump(mode="json")


def load_gate_evidence(path: str | Path) -> GateEvidence:
    """Load and validate one evidence document."""
    evidence_path = Path(path).expanduser().resolve()
    content = json.loads(evidence_path.read_text(encoding="utf-8"))
    return GateEvidence.model_validate(content)


def evidence_paths(directory: str | Path) -> tuple[Path, ...]:
    """Return only conventionally named mandatory-gate reports that exist."""
    evidence_directory = Path(directory).expanduser().resolve()
    return tuple(
        path
        for gate_id in REQUIRED_RELEASE_GATES
        if (path := evidence_directory / f"{gate_id}.json").is_file()
    )


def audit_release_evidence(
    paths: Iterable[str | Path],
    *,
    expected_version: str = __version__,
) -> ReleaseAudit:
    """Audit available reports without treating absent native execution as success."""
    reports: dict[str, tuple[Path, GateEvidence]] = {}
    invalid_by_gate: dict[str, tuple[Path, str]] = {}
    ignored: list[str] = []

    for raw_path in sorted((Path(path).expanduser().resolve() for path in paths), key=str):
        try:
            evidence = load_gate_evidence(raw_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            ignored.append(f"{raw_path.name}: {exc}")
            continue
        if evidence.gate_id not in REQUIRED_RELEASE_GATES:
            ignored.append(f"{raw_path.name}: unknown gate {evidence.gate_id!r}")
            continue
        if evidence.gate_id in reports or evidence.gate_id in invalid_by_gate:
            invalid_by_gate[evidence.gate_id] = (
                raw_path,
                f"Duplicate evidence for gate {evidence.gate_id!r}.",
            )
            reports.pop(evidence.gate_id, None)
            continue
        if evidence.application_version != expected_version:
            invalid_by_gate[evidence.gate_id] = (
                raw_path,
                (
                    f"Evidence version {evidence.application_version!r} does not match "
                    f"application version {expected_version!r}."
                ),
            )
            continue
        reports[evidence.gate_id] = (raw_path, evidence)

    gates: list[GateAudit] = []
    for gate_id in REQUIRED_RELEASE_GATES:
        invalid = invalid_by_gate.get(gate_id)
        if invalid is not None:
            path, reason = invalid
            gates.append(
                GateAudit(
                    gate_id=gate_id,
                    status="invalid",
                    evidence_path=path.name,
                    reason=reason,
                )
            )
            continue
        report = reports.get(gate_id)
        if report is None:
            gates.append(
                GateAudit(
                    gate_id=gate_id,
                    status="missing",
                    reason="No evidence document was supplied.",
                )
            )
            continue
        path, evidence = report
        gates.append(
            GateAudit(
                gate_id=gate_id,
                status=evidence.status,
                evidence_path=path.name,
                reason=(
                    "All recorded checks passed."
                    if evidence.status == "passed"
                    else "The gate has not passed; inspect its evidence checks."
                ),
            )
        )

    return ReleaseAudit(
        application_version=expected_version,
        candidate_ready=all(gate.status == "passed" for gate in gates),
        gates=tuple(gates),
        ignored_files=tuple(ignored),
    )
