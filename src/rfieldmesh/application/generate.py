"""End-to-end random-field generation and Abaqus assignment workflow."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import tempfile
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np

from rfieldmesh import __version__
from rfieldmesh.abaqus.geometry import structured_region_2d
from rfieldmesh.abaqus.parser import parse_abaqus_model
from rfieldmesh.abaqus.regions import ResolvedRegion, resolve_region
from rfieldmesh.abaqus.validation import OutputValidation, validate_generated_output
from rfieldmesh.abaqus.writer import AssignmentResult, write_elementwise_materials
from rfieldmesh.config.enums import (
    CorrelationKind,
    DistributionKind,
    GenerationAlgorithm,
    MappingMethod,
    PropertyKind,
)
from rfieldmesh.config.models import GenerationConfig, RandomVariableConfig
from rfieldmesh.exceptions import ConfigurationError, GeometryError, UnsafeWriteError
from rfieldmesh.random_fields.covariance_kl import PreparedCovarianceKL
from rfieldmesh.random_fields.marginals import apply_marginal
from rfieldmesh.random_fields.rng import rng_for_realization
from rfieldmesh.random_fields.spectral import PreparedSpectralExponential2D
from rfieldmesh.random_fields.statistics import FieldStatistics, field_statistics


@dataclass(frozen=True, slots=True)
class FieldGeneration:
    """One generated physical property aligned to eligible element labels."""

    property_kind: PropertyKind
    algorithm: GenerationAlgorithm
    values: dict[int, float]
    statistics: FieldStatistics
    diagnostics: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Complete output, manifest, fields, and independent validation."""

    assignment: AssignmentResult
    validation: OutputValidation
    manifest_path: Path
    manifest_sha256: str
    fields: tuple[FieldGeneration, ...]


def _diagnostics_dict(diagnostics: object) -> dict[str, Any]:
    if is_dataclass(diagnostics) and not isinstance(diagnostics, type):
        return asdict(diagnostics)
    return {"description": repr(diagnostics)}


def _try_structured(region: ResolvedRegion) -> bool:
    try:
        structured_region_2d(region)
    except GeometryError:
        return False
    return True


def _resolve_algorithm(
    requested: GenerationAlgorithm,
    region: ResolvedRegion,
    variable: RandomVariableConfig,
) -> GenerationAlgorithm:
    if requested is not GenerationAlgorithm.AUTO:
        return requested
    if (
        region.dimension == 2
        and variable.correlation.model is CorrelationKind.EXPONENTIAL
        and variable.distribution is not DistributionKind.TRUNCATED_NORMAL
        and _try_structured(region)
    ):
        return GenerationAlgorithm.SPECTRAL
    return GenerationAlgorithm.COVARIANCE_KL


def generate_property_field(
    region: ResolvedRegion,
    variable: RandomVariableConfig,
    config: GenerationConfig,
) -> FieldGeneration:
    """Generate one field using the selected or automatically resolved algorithm."""
    root_seed = config.first_seed if variable.seed is None else variable.seed
    rng = rng_for_realization(
        root_seed,
        config.realization_index,
        variable.property_kind,
        config.seed_strategy,
    )
    algorithm = _resolve_algorithm(config.algorithm, region, variable)
    if algorithm is GenerationAlgorithm.SPECTRAL:
        if variable.correlation.model is not CorrelationKind.EXPONENTIAL:
            raise ConfigurationError(
                "The Phase 4 spectral method supports exponential correlation only."
            )
        structured = structured_region_2d(region)
        spectral_mapping = (
            MappingMethod.RECTANGULAR_GAUSSIAN_AVERAGE
            if config.mapping is MappingMethod.AUTO
            else config.mapping
        )
        prepared = PreparedSpectralExponential2D.prepare(
            structured.grid,
            cast(tuple[float, float], variable.correlation.scales),
            mapping=spectral_mapping,
            config=config.spectral,
        )
        latent = prepared.generate(rng)
        physical_grid = apply_marginal(
            latent.values,
            variable.moments,
            variable.distribution,
            bounds=variable.bounds,
            latent_variance=latent.latent_variance,
        )
        values = {
            int(structured.labels[index]): float(physical_grid[index])
            for index in np.ndindex(structured.labels.shape)
        }
    elif algorithm is GenerationAlgorithm.COVARIANCE_KL:
        if config.mapping not in (MappingMethod.AUTO, MappingMethod.CENTROID_SAMPLE):
            raise ConfigurationError(
                "Covariance/KL uses centroid sampling in the Phase 4 checkpoint."
            )
        prepared_kl = PreparedCovarianceKL.prepare(
            region.representative_coordinates,
            variable.correlation,
            config=config.covariance_kl,
        )
        latent = prepared_kl.generate(rng)
        physical_values = apply_marginal(
            latent.values,
            variable.moments,
            variable.distribution,
            bounds=variable.bounds,
            latent_variance=latent.latent_variance,
        )
        values = {
            label: float(value)
            for label, value in zip(
                region.eligible_labels,
                physical_values,
                strict=True,
            )
        }
    else:  # pragma: no cover - enum and resolver protect this branch
        raise ConfigurationError(f"Unsupported generation algorithm: {algorithm}")
    ordered_values = np.asarray(
        [values[label] for label in region.eligible_labels],
        dtype=np.float64,
    )
    return FieldGeneration(
        property_kind=variable.property_kind,
        algorithm=algorithm,
        values=values,
        statistics=field_statistics(
            ordered_values,
            target_mean=variable.moments.mean,
            target_standard_deviation=variable.moments.standard_deviation,
        ),
        diagnostics=_diagnostics_dict(latent.diagnostics),
    )


def _write_json_atomic(path: Path, content: dict[str, Any], overwrite: bool) -> str:
    if path.exists() and not overwrite:
        raise UnsafeWriteError(f"Manifest already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(content, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )
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
                raise UnsafeWriteError(f"Manifest already exists: {path}") from exc
            os.unlink(temporary_name)
    except (OSError, UnsafeWriteError) as exc:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        if isinstance(exc, UnsafeWriteError):
            raise
        raise UnsafeWriteError(f"Could not write manifest: {path}") from exc
    return hashlib.sha256(payload).hexdigest()


def generate_model(config: GenerationConfig) -> GenerationResult:
    """Generate configured fields, write a model, reparse it, and save a manifest."""
    requested_output = Path(config.output_path).expanduser().resolve()
    manifest_path = (
        Path(config.manifest_path).expanduser().resolve()
        if config.manifest_path is not None
        else requested_output.with_suffix(".rfieldmesh.json")
    )
    requested_source = Path(config.source_path).expanduser().resolve()
    if requested_output == requested_source:
        raise UnsafeWriteError("The generated model must not overwrite its source file.")
    if manifest_path in (requested_source, requested_output):
        raise UnsafeWriteError("The manifest path must differ from source and model paths.")
    if not config.overwrite:
        for path in (requested_output, manifest_path):
            if path.exists():
                raise UnsafeWriteError(f"Output already exists: {path}")
    model = parse_abaqus_model(config.source_path)
    region = resolve_region(
        model,
        part_name=config.part_name,
        set_name=config.set_name,
        instance_name=config.instance_name,
    )
    fields = tuple(
        generate_property_field(region, variable, config) for variable in config.variables
    )
    by_kind = {field.property_kind: field.values for field in fields}
    assignment = write_elementwise_materials(
        model,
        region,
        config.output_path,
        youngs_modulus=by_kind.get(PropertyKind.YOUNGS_MODULUS),
        density=by_kind.get(PropertyKind.DENSITY),
        name_prefix=config.name_prefix,
        overwrite=config.overwrite,
    )
    validation = validate_generated_output(
        assignment,
        expected_youngs_modulus=by_kind.get(PropertyKind.YOUNGS_MODULUS),
        expected_density=by_kind.get(PropertyKind.DENSITY),
    )
    serialized_config = config.model_dump(mode="json")
    serialized_config["source_path"] = Path(config.source_path).name
    serialized_config["output_path"] = Path(config.output_path).name
    if serialized_config["manifest_path"] is not None:
        serialized_config["manifest_path"] = Path(
            cast(str, serialized_config["manifest_path"])
        ).name
    manifest = {
        "schema_version": "1.0",
        "application_version": __version__,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source": {
            "filename": model.source.path.name,
            "sha256": model.source.sha256,
            "size_bytes": model.source.size_bytes,
        },
        "output": {
            "filename": assignment.output_path.name,
            "sha256": assignment.output_sha256,
            "size_bytes": assignment.output_size_bytes,
        },
        "configuration": serialized_config,
        "environment": {
            "python": platform.python_version(),
            "dependencies": {
                package: importlib.metadata.version(package)
                for package in ("numpy", "pydantic", "scipy")
            },
        },
        "region": {
            "part": region.part.name,
            "instance": None if region.instance is None else region.instance.name,
            "set": region.set_name,
            "selected_count": len(region.selected_labels),
            "eligible_count": len(region.eligible_labels),
            "excluded_by_type": region.excluded_by_type,
            "region_origin": region.region_origin.tolist(),
            "coordinate_frame": "assembly_axes_region_local_origin",
            "source_material": region.coverage.source_material_name,
            "section_remainder_count": len(region.coverage.remainder_labels),
        },
        "fields": [
            {
                "property_kind": field.property_kind.value,
                "algorithm": field.algorithm.value,
                "statistics": field.statistics.as_dict(),
                "diagnostics": field.diagnostics,
                "values_by_element": field.values,
            }
            for field in fields
        ],
        "assignment": {
            "strategy": "material_per_element",
            "generated_material_count": len(assignment.generated_material_names),
            "generated_section_count": len(assignment.generated_set_names),
            "material_names_by_element": assignment.generated_material_names,
            "set_names_by_element": assignment.generated_set_names,
            "remainder_set": assignment.remainder_set_name,
        },
        "validation": asdict(validation),
    }
    manifest_sha256 = _write_json_atomic(
        manifest_path,
        manifest,
        overwrite=config.overwrite,
    )
    return GenerationResult(
        assignment=assignment,
        validation=validation,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha256,
        fields=fields,
    )
