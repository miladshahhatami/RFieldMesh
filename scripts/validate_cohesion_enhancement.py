"""Validate the committed six-property representative outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rfieldmesh import __version__
from rfieldmesh.abaqus.parser import parse_abaqus_model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "validation" / "output"
MODELS = ROOT / "validation" / "representative_models"
PROPERTY_ORDER = [
    "elastic_modulus",
    "density",
    "poissons_ratio",
    "friction_angle",
    "dilation_angle",
    "cohesion",
]
CASES = (
    {
        "name": "2D-Model_all_six",
        "legacy": "2D-Model_all_five",
        "source": "2D-Model.inp",
        "source_sha256": "bdcf0f4997b95da80b88a28e90ddc1d59a5e2b48a73270520a6e9666c37ba1e3",
        "source_material": "Soil",
        "source_cohesion": 5000.0,
        "eligible": 20_000,
        "remainder": 0,
        "algorithm": "spectral",
    },
    {
        "name": "3D-Model_Layer1_all_six",
        "legacy": "3D-Model_Layer1_all_five",
        "source": "3D-Model.inp",
        "source_sha256": "ff605ff694c03a1644285c465139ef6042290482baa7b15a74a22370f1747454",
        "source_material": "Layer1",
        "source_cohesion": 15_000.0,
        "eligible": 10_032,
        "remainder": 600,
        "algorithm": "covariance_kl",
    },
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(stem: str) -> dict[str, Any]:
    return json.loads((OUTPUT / f"{stem}.rfieldmesh.json").read_text(encoding="utf-8"))


def main() -> None:
    results: list[dict[str, Any]] = []
    for case in CASES:
        name = str(case["name"])
        manifest = _manifest(name)
        legacy = _manifest(str(case["legacy"]))
        source = MODELS / str(case["source"])
        output = OUTPUT / f"{name}.inp"
        fields = {field["property_kind"]: field for field in manifest["fields"]}
        legacy_fields = {field["property_kind"]: field for field in legacy["fields"]}

        assert __version__ == "1.0.0"
        assert manifest["application_version"] == "1.0.0"
        assert _sha256(source) == case["source_sha256"] == manifest["source"]["sha256"]
        assert _sha256(output) == manifest["output"]["sha256"]
        assert list(fields) == PROPERTY_ORDER
        assert manifest["validation"]["checked_properties"] == PROPERTY_ORDER
        assert manifest["validation"]["checked_elements"] == case["eligible"]
        assert manifest["validation"]["remainder_count"] == case["remainder"]
        assert fields["cohesion"]["algorithm"] == case["algorithm"]
        assert min(float(value) for value in fields["cohesion"]["values_by_element"].values()) >= 0
        assert all(
            fields[kind]["values_by_element"] == legacy_fields[kind]["values_by_element"]
            for kind in legacy_fields
        )

        source_model = parse_abaqus_model(source)
        output_model = parse_abaqus_model(output)
        assert (
            source_model.material(str(case["source_material"])).cohesion == case["source_cohesion"]
        )
        assert (
            output_model.material(str(case["source_material"])).cohesion == case["source_cohesion"]
        )
        first_name = next(iter(manifest["assignment"]["material_names_by_element"].values()))
        assert output_model.material(first_name).cohesion is not None

        results.append(
            {
                "case": name,
                "status": "passed",
                "eligible_elements": case["eligible"],
                "remainder_elements": case["remainder"],
                "algorithm": case["algorithm"],
                "output_sha256": manifest["output"]["sha256"],
                "legacy_fields_exactly_unchanged": True,
            }
        )
    print(json.dumps({"application_version": __version__, "cases": results}, indent=2))


if __name__ == "__main__":
    main()
