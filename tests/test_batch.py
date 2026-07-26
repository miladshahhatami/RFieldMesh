"""Batch planning, generation, and cancellation tests."""

import json
from pathlib import Path

import pytest

from rfieldmesh.application.batch import plan_batch, run_batch
from rfieldmesh.config.enums import DistributionKind, PropertyKind, SeedStrategy
from rfieldmesh.config.models import (
    BatchConfig,
    CorrelationConfig,
    GenerationConfig,
    MomentSpecification,
    RandomVariableConfig,
)
from rfieldmesh.exceptions import BatchConfigurationError
from rfieldmesh.infrastructure.concurrency import CancellationToken


def generation_config(source: Path, output: Path) -> GenerationConfig:
    """Return a compact deterministic generation request."""
    return GenerationConfig(
        source_path=str(source),
        output_path=str(output),
        part_name="Soil Part",
        set_name="Target",
        variables=(
            RandomVariableConfig(
                property_kind=PropertyKind.YOUNGS_MODULUS,
                moments=MomentSpecification(mean=2.0e7, standard_deviation=4.0e6),
                distribution=DistributionKind.LOGNORMAL,
                correlation=CorrelationConfig(scales=(2.0, 1.0)),
            ),
        ),
    )


def test_batch_generates_unique_models_manifests_and_summary(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    output_directory = tmp_path / "batch"
    updates = []
    config = BatchConfig(
        generation=generation_config(small_inp, tmp_path / "ignored.inp"),
        output_directory=str(output_directory),
        realization_count=2,
        start_index=3,
        filename_template="case_{index:02d}_seed{seed}.inp",
    )
    result = run_batch(config, progress=updates.append)
    assert result.completed_count == 2
    assert result.failed_count == 0
    assert not result.cancelled
    assert [item.realization_index for item in result.items] == [3, 4]
    assert [item.display_seed for item in result.items] == [1406, 1407]
    assert len(updates) == 4
    assert all(Path(item.output_path).exists() for item in result.items)
    assert all(Path(item.manifest_path).exists() for item in result.items)

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["completed_count"] == 2
    assert summary["items"][0]["status"] == "completed"
    assert len(result.summary_sha256) == 64


def test_batch_preflight_rejects_nonunique_spawn_seed_names(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    generation = generation_config(small_inp, tmp_path / "ignored.inp").model_copy(
        update={"seed_strategy": SeedStrategy.SPAWN}
    )
    config = BatchConfig(
        generation=generation,
        output_directory=str(tmp_path / "batch"),
        realization_count=2,
        filename_template="case_seed{seed}.inp",
    )
    with pytest.raises(BatchConfigurationError, match="unique"):
        plan_batch(config)


def test_precancelled_batch_writes_summary_but_no_models(
    small_inp: Path,
    tmp_path: Path,
) -> None:
    token = CancellationToken()
    token.cancel()
    config = BatchConfig(
        generation=generation_config(small_inp, tmp_path / "ignored.inp"),
        output_directory=str(tmp_path / "cancelled"),
        realization_count=3,
    )
    result = run_batch(config, cancellation=token)
    assert result.cancelled
    assert result.items == ()
    assert result.summary_path.exists()
    assert not tuple((tmp_path / "cancelled").glob("*.inp"))
