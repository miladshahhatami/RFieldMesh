"""Stable 1.0.0 metadata and publication-asset tests."""

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_stable_version_metadata_is_consistent() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == "1.0.0"
    assert "Development Status :: 5 - Production/Stable" in pyproject["project"]["classifiers"]

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(r"^version:\s*1\.0\.0\s*$", citation, flags=re.MULTILINE)
    assert "Milad" in citation
    assert "Shah Hatami" in citation
    assert "## 1.0.0 — Stable release" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_stable_public_documents_are_present() -> None:
    required = (
        "RELEASE_NOTES_1.0.0.md",
        "KNOWN_LIMITATIONS.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "docs/user_guide/quickstart.md",
        "docs/release/phase7_stable_release.md",
        "docs/release/publication_checklist.md",
        "docs/developer_guide/release_process.md",
        "docs/publication/manuscript_limitations.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/workflows/source-quality.yml",
    )
    assert all((ROOT / path).is_file() for path in required)


def test_large_mesh_limit_is_disclosed_for_users_and_manuscripts() -> None:
    content = "\n".join(
        (ROOT / path).read_text(encoding="utf-8").lower()
        for path in (
            "README.md",
            "KNOWN_LIMITATIONS.md",
            "docs/publication/manuscript_limitations.md",
        )
    )
    for term in ("karhunen", "quadratic", "axis-aligned", "rotated", "unstructured"):
        assert term in content


def test_promotion_record_does_not_mislabel_attestation_as_machine_evidence() -> None:
    record = json.loads(
        (ROOT / "validation/stable_release/promotion_record.json").read_text(encoding="utf-8")
    )
    assert record["application_version"] == "1.0.0"
    assert record["promotion_source_version"] == "0.9.0rc1"
    assert record["scientific_core_changed_during_promotion"] is False
    assert record["native_validation"]["status"] == "user_attested"
    assert record["native_validation"]["machine_evidence_uploaded"] is False


def test_windows_build_distributes_stable_documents() -> None:
    build = (ROOT / "packaging/windows/build.ps1").read_text(encoding="utf-8")
    assert 'Copy-Item "RELEASE_NOTES_1.0.0.md"' in build
    assert 'Copy-Item "KNOWN_LIMITATIONS.md"' in build
    assert 'Copy-Item "CITATION.cff"' in build
    assert "RELEASE_NOTES_PHASE6.md" not in build
