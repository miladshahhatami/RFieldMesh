"""Byte-preserving Abaqus source-file representation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from rfieldmesh.exceptions import AbaqusParseError, UnsafeWriteError


@dataclass(frozen=True, slots=True)
class AbaqusSource:
    """Decoded source text together with the information needed for exact output."""

    path: Path
    text: str
    encoding: str
    bom: bytes
    newline: str
    terminal_newline: bool
    sha256: str
    size_bytes: int

    @classmethod
    def read(cls, path: str | Path) -> AbaqusSource:
        """Read an input file without normalizing its text representation."""
        source_path = Path(path).expanduser().resolve()
        try:
            payload = source_path.read_bytes()
        except OSError as exc:
            raise AbaqusParseError(f"Could not read Abaqus input file: {source_path}") from exc

        bom = b""
        encoding = "utf-8"
        content = payload
        if payload.startswith(b"\xef\xbb\xbf"):
            bom = b"\xef\xbb\xbf"
            content = payload[len(bom) :]
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            encoding = "latin-1"
            text = content.decode(encoding)

        crlf = text.count("\r\n")
        bare_lf = text.count("\n") - crlf
        bare_cr = text.count("\r") - crlf
        if crlf >= bare_lf and crlf >= bare_cr and crlf:
            newline = "\r\n"
        elif bare_lf >= bare_cr and bare_lf:
            newline = "\n"
        elif bare_cr:
            newline = "\r"
        else:
            newline = "\n"

        return cls(
            path=source_path,
            text=text,
            encoding=encoding,
            bom=bom,
            newline=newline,
            terminal_newline=text.endswith(("\n", "\r")),
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )

    def encode(self, text: str) -> bytes:
        """Encode modified text using the source encoding and byte-order mark."""
        return self.bom + text.encode(self.encoding)

    def verify_unchanged(self) -> None:
        """Refuse to patch a source file that changed after parsing."""
        try:
            current = self.path.read_bytes()
        except OSError as exc:
            raise UnsafeWriteError(f"Could not re-read source file: {self.path}") from exc
        if hashlib.sha256(current).hexdigest() != self.sha256:
            raise UnsafeWriteError(
                "The Abaqus source file changed after inspection; parse it again before writing."
            )
