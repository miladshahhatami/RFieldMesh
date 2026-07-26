"""Render pip-licenses JSON without build-host absolute paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render(records: list[dict[str, Any]]) -> str:
    """Return a deterministic human-readable dependency licence inventory."""
    sections = [
        "# Python package licence inventory",
        "",
        (
            "This inventory records the exact environment used for this build. "
            "Absolute build-host paths are intentionally omitted."
        ),
        "",
    ]
    for record in sorted(records, key=lambda item: str(item["Name"]).casefold()):
        sections.extend(
            [
                f"## {record['Name']} {record['Version']}",
                "",
                f"Declared licence: {record['License']}",
                "",
                "Licence text:",
                "",
                str(record.get("LicenseText", "UNKNOWN")).strip(),
                "",
            ]
        )
    return "\n".join(sections).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    records = json.loads(arguments.input.read_text(encoding="utf-8-sig"))
    if not isinstance(records, list):
        raise ValueError("pip-licenses JSON must contain a list.")
    content = render(records)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
