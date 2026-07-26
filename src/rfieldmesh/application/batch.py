"""Collision-safe, cancellable multi-realization generation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from rfieldmesh.application.generate import GenerationResult, generate_model
from rfieldmesh.config.enums import SeedStrategy
from rfieldmesh.config.models import BatchConfig, GenerationConfig
from rfieldmesh.exceptions import BatchConfigurationError, RFieldMeshError, UnsafeWriteError
from rfieldmesh.infrastructure.atomic_files import write_json_atomic
from rfieldmesh.infrastructure.concurrency import CancellationToken

BatchStatus = Literal["completed", "failed"]


@dataclass(frozen=True, slots=True)
class PlannedRealization:
    """One preflighted realization and its output locations."""

    realization_index: int
    display_seed: int
    output_path: Path
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class BatchProgress:
    """Progress notification suitable for CLI and GUI presentation."""

    completed: int
    total: int
    realization_index: int
    stage: Literal["starting", "completed", "failed"]
    message: str


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    """Outcome for one attempted realization."""

    realization_index: int
    display_seed: int
    output_path: str
    manifest_path: str
    status: BatchStatus
    output_sha256: str | None
    manifest_sha256: str | None
    checked_elements: int | None
    error: str | None


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Complete batch outcome and summary-file provenance."""

    items: tuple[BatchItemResult, ...]
    requested_count: int
    completed_count: int
    failed_count: int
    cancelled: bool
    summary_path: Path
    summary_sha256: str


ProgressCallback = Callable[[BatchProgress], None]


def _display_seed(config: GenerationConfig, index: int) -> int:
    if config.seed_strategy is SeedStrategy.LINEAR:
        return config.first_seed + index
    return config.first_seed


def _render_filename(template: str, *, index: int, seed: int) -> str:
    try:
        rendered = template.format(
            index=index,
            realization=index,
            seed=seed,
        )
    except (KeyError, IndexError, ValueError) as exc:
        raise BatchConfigurationError(
            "Batch filenames may use only {index}, {realization}, and {seed}."
        ) from exc
    if (
        not rendered
        or rendered in {".", ".."}
        or "/" in rendered
        or "\\" in rendered
        or not rendered.casefold().endswith(".inp")
    ):
        raise BatchConfigurationError(
            f"The filename template produced an unsafe Abaqus filename: {rendered!r}."
        )
    return rendered


def plan_batch(config: BatchConfig) -> tuple[PlannedRealization, ...]:
    """Resolve and validate all batch paths before generation begins."""
    output_directory = Path(config.output_directory).expanduser().resolve()
    planned: list[PlannedRealization] = []
    occupied: set[Path] = set()
    source = Path(config.generation.source_path).expanduser().resolve()
    for offset in range(config.realization_count):
        index = config.start_index + offset
        display_seed = _display_seed(config.generation, index)
        filename = _render_filename(
            config.filename_template,
            index=index,
            seed=display_seed,
        )
        output = (output_directory / filename).resolve()
        if output.parent != output_directory:
            raise BatchConfigurationError("A batch output escaped its configured directory.")
        manifest = output.with_suffix(".rfieldmesh.json")
        if output == source or manifest == source:
            raise BatchConfigurationError("A batch output would overwrite the source model.")
        if output in occupied or manifest in occupied:
            raise BatchConfigurationError(
                "The filename template does not produce unique realization paths."
            )
        occupied.update((output, manifest))
        planned.append(
            PlannedRealization(
                realization_index=index,
                display_seed=display_seed,
                output_path=output,
                manifest_path=manifest,
            )
        )

    summary = (
        Path(config.summary_path).expanduser().resolve()
        if config.summary_path is not None
        else output_directory / "rfieldmesh_batch_summary.json"
    )
    if summary in occupied or summary == source:
        raise BatchConfigurationError("The batch summary path collides with a model path.")
    if not config.generation.overwrite:
        collisions = [
            path
            for item in planned
            for path in (item.output_path, item.manifest_path)
            if path.exists()
        ]
        if summary.exists():
            collisions.append(summary)
        if collisions:
            raise UnsafeWriteError(
                f"{len(collisions)} planned batch output(s) already exist; "
                f"the first is {collisions[0]}."
            )
    return tuple(planned)


def _completed_item(
    plan: PlannedRealization,
    result: GenerationResult,
) -> BatchItemResult:
    return BatchItemResult(
        realization_index=plan.realization_index,
        display_seed=plan.display_seed,
        output_path=str(result.assignment.output_path),
        manifest_path=str(result.manifest_path),
        status="completed",
        output_sha256=result.assignment.output_sha256,
        manifest_sha256=result.manifest_sha256,
        checked_elements=result.validation.checked_elements,
        error=None,
    )


def _failed_item(plan: PlannedRealization, error: Exception) -> BatchItemResult:
    return BatchItemResult(
        realization_index=plan.realization_index,
        display_seed=plan.display_seed,
        output_path=str(plan.output_path),
        manifest_path=str(plan.manifest_path),
        status="failed",
        output_sha256=None,
        manifest_sha256=None,
        checked_elements=None,
        error=str(error),
    )


def run_batch(
    config: BatchConfig,
    *,
    cancellation: CancellationToken | None = None,
    progress: ProgressCallback | None = None,
) -> BatchResult:
    """Generate a preflighted batch sequentially with cooperative cancellation."""
    plans = plan_batch(config)
    token = cancellation if cancellation is not None else CancellationToken()
    items: list[BatchItemResult] = []
    for plan in plans:
        if token.is_cancelled:
            break
        if progress is not None:
            progress(
                BatchProgress(
                    completed=len(items),
                    total=len(plans),
                    realization_index=plan.realization_index,
                    stage="starting",
                    message=f"Generating realization {plan.realization_index}.",
                )
            )
        generation = config.generation.model_copy(
            update={
                "output_path": str(plan.output_path),
                "manifest_path": str(plan.manifest_path),
                "realization_index": plan.realization_index,
            }
        )
        try:
            result = generate_model(generation)
        except (OSError, RFieldMeshError) as exc:
            item = _failed_item(plan, exc)
            items.append(item)
            if progress is not None:
                progress(
                    BatchProgress(
                        completed=len(items),
                        total=len(plans),
                        realization_index=plan.realization_index,
                        stage="failed",
                        message=str(exc),
                    )
                )
            if not config.continue_on_error:
                break
        else:
            item = _completed_item(plan, result)
            items.append(item)
            if progress is not None:
                progress(
                    BatchProgress(
                        completed=len(items),
                        total=len(plans),
                        realization_index=plan.realization_index,
                        stage="completed",
                        message=f"Completed realization {plan.realization_index}.",
                    )
                )

    completed = sum(item.status == "completed" for item in items)
    failed = sum(item.status == "failed" for item in items)
    cancelled = token.is_cancelled
    summary_path = (
        Path(config.summary_path).expanduser().resolve()
        if config.summary_path is not None
        else Path(config.output_directory).expanduser().resolve() / "rfieldmesh_batch_summary.json"
    )
    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "requested_count": config.realization_count,
        "attempted_count": len(items),
        "completed_count": completed,
        "failed_count": failed,
        "cancelled": cancelled,
        "start_index": config.start_index,
        "filename_template": config.filename_template,
        "items": [asdict(item) for item in items],
    }
    summary_sha256 = write_json_atomic(
        summary_path,
        summary,
        overwrite=config.generation.overwrite,
    )
    return BatchResult(
        items=tuple(items),
        requested_count=config.realization_count,
        completed_count=completed,
        failed_count=failed,
        cancelled=cancelled,
        summary_path=summary_path,
        summary_sha256=summary_sha256,
    )
