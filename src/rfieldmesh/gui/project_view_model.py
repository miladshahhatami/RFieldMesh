"""Qt-independent presentation state for the desktop interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rfieldmesh.application.batch import BatchResult, ProgressCallback, run_batch
from rfieldmesh.application.inspect_model import inspect_model
from rfieldmesh.application.preview import PreviewResult, preview_model
from rfieldmesh.config.models import BatchConfig, GenerationConfig
from rfieldmesh.infrastructure.concurrency import CancellationToken
from rfieldmesh.visualization.figures import preview_html


@dataclass(frozen=True, slots=True)
class PartOptions:
    """Region-selection choices derived from an inspected model."""

    name: str
    element_sets: tuple[str, ...]
    instances: tuple[str, ...]


class ProjectViewModel:
    """Own desktop workflow state and invoke application services."""

    def __init__(self) -> None:
        self.source_path: Path | None = None
        self.inspection: dict[str, Any] | None = None
        self.generation_config: GenerationConfig | None = None
        self.preview_result: PreviewResult | None = None
        self.batch_result: BatchResult | None = None

    def load_model(self, path: str | Path) -> dict[str, Any]:
        """Inspect a source model and reset dependent state."""
        source = Path(path).expanduser().resolve()
        inspection = inspect_model(source)
        self.source_path = source
        self.inspection = inspection
        self.generation_config = None
        self.preview_result = None
        self.batch_result = None
        return inspection

    def part_options(self) -> tuple[PartOptions, ...]:
        """Return parts, part-level sets, and compatible instances."""
        if self.inspection is None:
            return ()
        instances_by_part: dict[str, list[str]] = {}
        for instance in self.inspection["instances"]:
            instances_by_part.setdefault(str(instance["part"]), []).append(str(instance["name"]))
        return tuple(
            PartOptions(
                name=str(part["name"]),
                element_sets=tuple(str(name) for name in part["element_sets"]),
                instances=tuple(instances_by_part.get(str(part["name"]), ())),
            )
            for part in self.inspection["parts"]
        )

    def set_generation_config(self, config: GenerationConfig) -> None:
        """Validate that a configuration belongs to the loaded source model."""
        if self.source_path is None:
            raise RuntimeError("Load an Abaqus model before configuring generation.")
        if Path(config.source_path).expanduser().resolve() != self.source_path:
            raise ValueError("The generation configuration refers to another source model.")
        self.generation_config = config

    def create_preview(self, config: GenerationConfig) -> tuple[PreviewResult, str]:
        """Generate and render an unsaved preview."""
        self.set_generation_config(config)
        result = preview_model(config)
        rendered = preview_html(result)
        self.preview_result = result
        return result, rendered

    def generate_batch(
        self,
        config: BatchConfig,
        *,
        cancellation: CancellationToken | None = None,
        progress: ProgressCallback | None = None,
    ) -> BatchResult:
        """Generate a batch while retaining the final presentation state."""
        self.set_generation_config(config.generation)
        result = run_batch(
            config,
            cancellation=cancellation,
            progress=progress,
        )
        self.batch_result = result
        return result
