"""GUI-independent application workflows."""

from rfieldmesh.application.batch import BatchResult, run_batch
from rfieldmesh.application.generate import (
    FieldGeneration,
    GenerationResult,
    generate_model,
    generate_property_field,
)
from rfieldmesh.application.inspect_model import inspect_model
from rfieldmesh.application.preview import PreviewResult, preview_model

__all__ = [
    "BatchResult",
    "FieldGeneration",
    "GenerationResult",
    "PreviewResult",
    "generate_model",
    "generate_property_field",
    "inspect_model",
    "preview_model",
    "run_batch",
]
