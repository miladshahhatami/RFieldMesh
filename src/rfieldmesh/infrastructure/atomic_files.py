"""Small atomic-publication helpers for reports and summaries."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rfieldmesh.exceptions import UnsafeWriteError


def _publish_bytes(path: Path, payload: bytes, *, overwrite: bool) -> str:
    if path.exists() and not overwrite:
        raise UnsafeWriteError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        if overwrite:
            os.replace(temporary_name, path)
        else:
            try:
                os.link(temporary_name, path)
            except FileExistsError as exc:
                raise UnsafeWriteError(f"Output already exists: {path}") from exc
            os.unlink(temporary_name)
    except (OSError, UnsafeWriteError) as exc:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        if isinstance(exc, UnsafeWriteError):
            raise
        raise UnsafeWriteError(f"Could not write output: {path}") from exc
    return hashlib.sha256(payload).hexdigest()


def write_text_atomic(
    path: str | Path,
    content: str,
    *,
    overwrite: bool = False,
    encoding: str = "utf-8",
) -> str:
    """Publish text atomically and return the content SHA-256 checksum."""
    destination = Path(path).expanduser().resolve()
    return _publish_bytes(destination, content.encode(encoding), overwrite=overwrite)


def write_json_atomic(
    path: str | Path,
    content: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> str:
    """Publish deterministic JSON atomically and return its SHA-256 checksum."""
    payload = json.dumps(
        content,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    return write_text_atomic(path, payload + "\n", overwrite=overwrite)
