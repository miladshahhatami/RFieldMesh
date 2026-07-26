"""Tokenizer for Abaqus star-keyword input files."""

from __future__ import annotations

import re

from rfieldmesh.abaqus.source import AbaqusSource
from rfieldmesh.abaqus.tokens import KeywordToken, readonly_parameters
from rfieldmesh.exceptions import AbaqusParseError

_LINE_PATTERN = re.compile(r".*?(?:\r\n|\n|\r|$)")


def _split_header(header: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    quoted = False
    for character in header:
        if character == '"':
            quoted = not quoted
            current.append(character)
        elif character == "," and not quoted:
            fields.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    fields.append("".join(current).strip())
    if quoted:
        raise AbaqusParseError(f"Unterminated quote in Abaqus keyword header: {header!r}")
    return fields


def _parse_header(header: str) -> tuple[str, str, dict[str, str | None]]:
    stripped = header.strip()
    fields = _split_header(stripped)
    raw_keyword = fields[0][1:].strip()
    if not raw_keyword:
        raise AbaqusParseError("An empty Abaqus keyword was encountered.")
    parameters: dict[str, str | None] = {}
    for field in fields[1:]:
        if not field:
            continue
        if "=" in field:
            key, value = field.split("=", 1)
            parameters[key.strip().casefold()] = value.strip().strip('"')
        else:
            parameters[field.strip().casefold()] = None
    return raw_keyword.casefold(), raw_keyword, parameters


def tokenize(source: AbaqusSource) -> tuple[KeywordToken, ...]:
    """Tokenize keyword headers and their data without rewriting source text."""
    line_spans: list[tuple[int, int, str]] = []
    for match in _LINE_PATTERN.finditer(source.text):
        line = match.group(0)
        if not line:
            continue
        line_spans.append((match.start(), match.end(), line))

    keyword_lines: list[tuple[int, int, str]] = []
    for start, end, line in line_spans:
        content = line.lstrip()
        if content.startswith("*") and not content.startswith("**"):
            header = line.rstrip("\r\n")
            keyword_lines.append((start, end, header))

    tokens: list[KeywordToken] = []
    for index, (start, header_end, header) in enumerate(keyword_lines):
        data_end = (
            keyword_lines[index + 1][0] if index + 1 < len(keyword_lines) else len(source.text)
        )
        keyword, raw_keyword, parameters = _parse_header(header.lstrip())
        tokens.append(
            KeywordToken(
                index=index,
                keyword=keyword,
                raw_keyword=raw_keyword,
                parameters=readonly_parameters(parameters),
                start=start,
                header_end=header_end,
                data_start=header_end,
                data_end=data_end,
            )
        )
    return tuple(tokens)
