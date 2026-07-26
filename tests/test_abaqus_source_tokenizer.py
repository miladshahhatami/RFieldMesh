"""Source-preservation and tokenization tests."""

from pathlib import Path

from rfieldmesh.abaqus.source import AbaqusSource
from rfieldmesh.abaqus.tokenizer import tokenize


def test_source_round_trip_preserves_crlf_and_bytes(small_inp: Path) -> None:
    source = AbaqusSource.read(small_inp)
    assert source.newline == "\r\n"
    assert source.terminal_newline
    assert source.encode(source.text) == small_inp.read_bytes()


def test_tokenizer_handles_quoted_names_and_flags(small_inp: Path) -> None:
    source = AbaqusSource.read(small_inp)
    tokens = tokenize(source)
    part = next(token for token in tokens if token.keyword == "part")
    generated_set = next(
        token
        for token in tokens
        if token.keyword == "elset" and token.parameter("elset") == "Target"
    )
    assert part.parameter("name") == "Soil Part"
    assert "generate" in generated_set.parameters
    assert generated_set.parameter("generate") is None
