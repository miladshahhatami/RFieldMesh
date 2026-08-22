"""Phase 8 manuscript, graphics, and deposition-metadata checks."""

import json
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        assert stream.read(8) == b"\x89PNG\r\n\x1a\n"
        length = struct.unpack(">I", stream.read(4))[0]
        assert stream.read(4) == b"IHDR"
        assert length == 13
        width, height = struct.unpack(">II", stream.read(8))
    return width, height


def test_publication_metadata_is_consistent_and_doi_safe() -> None:
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert zenodo["version"] == "1.0.0"
    assert zenodo["title"] in citation
    assert zenodo["license"] == "bsd-3-clause"
    assert "doi:" not in citation.lower()
    assert "github.com/" not in citation.lower()


def test_graphics_have_release_dimensions() -> None:
    assert _png_dimensions(ROOT / "docs/assets/rfieldmesh-social-preview.png") == (1200, 625)
    assert _png_dimensions(
        ROOT / "docs/publication/manuscript/rfieldmesh-graphical-abstract.png"
    ) == (1600, 900)


def test_manuscript_and_highlights_are_submission_ready() -> None:
    manuscript = (ROOT / "docs/publication/softwarex_manuscript.md").read_text(encoding="utf-8")
    highlights = [
        line.strip()
        for line in (ROOT / "docs/publication/HIGHLIGHTS.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert 3 <= len(highlights) <= 5
    assert all(len(line) <= 85 for line in highlights)
    for term in ("Software and data availability", "Limitations and future development"):
        assert term in manuscript
    for term in ("rotated", "skewed", "unstructured", "user attestation"):
        assert term in manuscript.lower()


def test_rendered_word_manuscript_is_a_valid_office_document() -> None:
    path = ROOT / "docs/publication/RFieldMesh_SoftwareX_Manuscript_v1.0.0.docx"
    assert path.stat().st_size > 100_000
    with zipfile.ZipFile(path) as archive:
        members = set(archive.namelist())
    assert "[Content_Types].xml" in members
    assert "word/document.xml" in members
    assert any(name.startswith("word/media/") for name in members)


def test_phase8_record_does_not_claim_external_publication() -> None:
    record = (ROOT / "docs/release/phase8_publication.md").read_text(encoding="utf-8")
    assert "External actions pending" in record
    assert "not evidence" in record
    assert "RFieldMesh-1.0.0-windows-x64.zip" in record
