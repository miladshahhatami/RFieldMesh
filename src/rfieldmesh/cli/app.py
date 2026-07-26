"""Typer command-line interface for inspection, preview, and generation workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from rfieldmesh.application.batch import run_batch
from rfieldmesh.application.generate import generate_model
from rfieldmesh.application.inspect_model import inspect_model
from rfieldmesh.application.preview import preview_model
from rfieldmesh.config.models import BatchConfig, GenerationConfig
from rfieldmesh.exceptions import RFieldMeshError
from rfieldmesh.infrastructure.atomic_files import write_json_atomic
from rfieldmesh.release.evidence import audit_release_evidence, evidence_paths
from rfieldmesh.visualization.figures import export_preview_html

app = typer.Typer(
    name="rfieldmesh",
    no_args_is_help=True,
    help="Generate reproducible mesh-based random fields for Abaqus input models.",
)


def _fail(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=2)


def _resolve_path(value: str, directory: Path) -> str:
    path = Path(value).expanduser()
    return str((path if path.is_absolute() else directory / path).resolve())


def _load_generation_config(project: Path) -> GenerationConfig:
    raw = json.loads(project.read_text(encoding="utf-8"))
    config = GenerationConfig.model_validate(raw)
    directory = project.parent
    return config.model_copy(
        update={
            "source_path": _resolve_path(config.source_path, directory),
            "output_path": _resolve_path(config.output_path, directory),
            "manifest_path": (
                None
                if config.manifest_path is None
                else _resolve_path(config.manifest_path, directory)
            ),
        }
    )


def _load_batch_config(project: Path) -> BatchConfig:
    raw = json.loads(project.read_text(encoding="utf-8"))
    config = BatchConfig.model_validate(raw)
    directory = project.parent
    generation = config.generation.model_copy(
        update={
            "source_path": _resolve_path(config.generation.source_path, directory),
            "output_path": _resolve_path(config.generation.output_path, directory),
            "manifest_path": (
                None
                if config.generation.manifest_path is None
                else _resolve_path(config.generation.manifest_path, directory)
            ),
        }
    )
    return config.model_copy(
        update={
            "generation": generation,
            "output_directory": _resolve_path(config.output_directory, directory),
            "summary_path": (
                None
                if config.summary_path is None
                else _resolve_path(config.summary_path, directory)
            ),
        }
    )


@app.command("inspect")
def inspect_command(
    source: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Abaqus .inp file to inspect.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            resolve_path=True,
            help="Optional JSON output file.",
        ),
    ] = None,
) -> None:
    """Inspect parts, instances, sets, elements, materials, and sections."""
    try:
        summary = inspect_model(source)
    except RFieldMeshError as exc:
        _fail(str(exc))
    serialized = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if output is None:
        typer.echo(serialized, nl=False)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        typer.echo(f"Inspection written to {output}")


@app.command("generate")
def generate_command(
    project: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Generation configuration in JSON format.",
        ),
    ],
) -> None:
    """Generate fields, write a model and manifest, then reparse the output."""
    try:
        config = _load_generation_config(project)
        result = generate_model(config)
    except (OSError, json.JSONDecodeError, ValidationError, RFieldMeshError) as exc:
        _fail(str(exc))
    typer.echo(f"Generated model: {result.assignment.output_path}")
    typer.echo(f"Manifest: {result.manifest_path}")
    typer.echo(f"Validated elements: {result.validation.checked_elements}")


@app.command("preview")
def preview_command(
    project: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Generation configuration in JSON format.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            resolve_path=True,
            help="Self-contained interactive HTML preview.",
        ),
    ] = Path("rfieldmesh_preview.html"),
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace an existing HTML preview."),
    ] = False,
) -> None:
    """Generate fields without an Abaqus write and export an interactive preview."""
    try:
        config = _load_generation_config(project)
        preview = preview_model(config)
        export_preview_html(preview, output, overwrite=overwrite)
    except (
        OSError,
        json.JSONDecodeError,
        ValidationError,
        RFieldMeshError,
    ) as exc:
        _fail(str(exc))
    typer.echo(f"Preview: {output}")
    typer.echo(f"Eligible elements: {preview.eligible_count}")
    typer.echo(f"Excluded elements: {preview.excluded_count}")


@app.command("batch")
def batch_command(
    project: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Batch configuration in JSON format.",
        ),
    ],
) -> None:
    """Generate multiple deterministic realizations and a batch summary."""
    try:
        config = _load_batch_config(project)
        result = run_batch(
            config,
            progress=lambda update: typer.echo(
                f"[{update.completed}/{update.total}] {update.message}"
            ),
        )
    except (
        OSError,
        json.JSONDecodeError,
        ValidationError,
        RFieldMeshError,
    ) as exc:
        _fail(str(exc))
    typer.echo(f"Generated realizations: {result.completed_count}")
    typer.echo(f"Failed realizations: {result.failed_count}")
    typer.echo(f"Batch summary: {result.summary_path}")
    if result.failed_count:
        raise typer.Exit(code=1)


@app.command("gui")
def gui_command() -> None:
    """Launch the optional PySide6 desktop application."""
    try:
        from rfieldmesh.gui.application import main as gui_main
    except ImportError as exc:
        _fail(f"Desktop dependencies are unavailable; install 'rfieldmesh[desktop]'. ({exc})")
    raise typer.Exit(code=gui_main())


@app.command("release-audit")
def release_audit_command(
    evidence_directory: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
            help="Directory containing JSON release-evidence documents.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            resolve_path=True,
            help="Optional JSON audit output.",
        ),
    ] = None,
    require_ready: Annotated[
        bool,
        typer.Option(
            "--require-ready",
            help="Return exit status 1 unless every mandatory release gate passed.",
        ),
    ] = False,
) -> None:
    """Audit native Windows, Abaqus, source-quality, and acceptance evidence."""
    audit = audit_release_evidence(evidence_paths(evidence_directory))
    serialized = json.dumps(audit.as_dict(), indent=2, sort_keys=True) + "\n"
    if output is None:
        typer.echo(serialized, nl=False)
    else:
        write_json_atomic(output, audit.as_dict(), overwrite=True)
        typer.echo(f"Release audit written to {output}")
    typer.echo(f"Candidate ready: {str(audit.candidate_ready).lower()}")
    if require_ready and not audit.candidate_ready:
        raise typer.Exit(code=1)


def main() -> None:
    """Console-script entry point."""
    app()
