"""Validate an RFieldMesh output through the native Abaqus/CAE kernel.

Run with:

    abaqus cae noGUI=validate_generated_model.py -- \
        --input generated.inp \
        --manifest generated.rfieldmesh.json \
        --report abaqus_report.json \
        --gate-id abaqus_import_2d \
        --mode import

This file deliberately uses only the Python standard library plus modules
provided by the Abaqus execution environment. It retains ``timezone.utc``
instead of the Python 3.11 ``UTC`` alias for Abaqus releases based on Python
3.10.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from abaqus import mdb, session
from abaqusConstants import ANALYSIS, OFF


def _arguments():
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--mode", choices=("import", "datacheck", "analysis"), required=True)
    parser.add_argument("--job-name")
    parser.add_argument("--work-directory", type=Path)
    parser.add_argument("--relative-tolerance", type=float, default=1.0e-10)
    return parser.parse_args(values)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check(checks, check_id, passed, details):
    checks.append(
        {
            "check_id": check_id,
            "passed": bool(passed),
            "details": str(details),
        }
    )
    if not passed:
        raise RuntimeError(details)


def _section_materials(part, model):
    materials_by_set = {}
    for assignment in part.sectionAssignments:
        region_name = assignment.region.name
        section = model.sections[assignment.sectionName]
        materials_by_set[region_name.casefold()] = section.material
    return materials_by_set


def _repository_item(repository, name, description):
    requested = name.casefold()
    for key in repository.keys():
        if str(key).casefold() == requested:
            return repository[key]
    raise RuntimeError(f"{description} is absent after import: {name}")


def _first_table_value(material, property_kind):
    if property_kind == "youngs_modulus":
        return float(material.elastic.table[0][0])
    if property_kind == "density":
        return float(material.density.table[0][0])
    raise RuntimeError(f"Unsupported property kind in manifest: {property_kind}")


def _validate_import(model, manifest, tolerance, checks):
    region = manifest["region"]
    assignment = manifest["assignment"]
    part_name = region["part"]
    part = _repository_item(model.parts, part_name, "Part")
    _check(checks, "part_present", True, f"Imported part: {part_name}")

    material_names = {
        int(label): name for label, name in assignment["material_names_by_element"].items()
    }
    set_names = {int(label): name for label, name in assignment["set_names_by_element"].items()}
    expected_count = int(region["eligible_count"])
    _check(
        checks,
        "generated_material_count",
        len(material_names) == expected_count,
        f"Expected and recorded generated material count: {expected_count}",
    )
    _check(
        checks,
        "generated_set_count",
        len(set_names) == expected_count,
        f"Expected and recorded generated set count: {expected_count}",
    )

    section_materials = _section_materials(part, model)
    for label, material_name in material_names.items():
        _repository_item(model.materials, material_name, "Generated material")
        set_name = set_names[label]
        element_set = _repository_item(part.sets, set_name, "Generated element set")
        element_count = len(element_set.elements)
        if element_count != 1:
            raise RuntimeError(
                f"Generated set {set_name} contains {element_count} elements instead of one."
            )
        actual_material = section_materials.get(set_name.casefold())
        if actual_material is None or actual_material.casefold() != material_name.casefold():
            raise RuntimeError(
                f"Generated set {set_name} uses {actual_material!r} instead of {material_name!r}."
            )

    expected_fields = {
        field["property_kind"]: {
            int(label): float(value) for label, value in field["values_by_element"].items()
        }
        for field in manifest["fields"]
    }
    for property_kind, values in expected_fields.items():
        for label, expected in values.items():
            material = _repository_item(
                model.materials,
                material_names[label],
                "Generated material",
            )
            actual = _first_table_value(material, property_kind)
            if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=0.0):
                raise RuntimeError(
                    f"{property_kind} differs for element {label}: "
                    f"imported={actual!r} expected={expected!r}"
                )
    _check(
        checks,
        "property_values",
        True,
        "Abaqus imported all configured material-property values within tolerance.",
    )
    _check(
        checks,
        "section_coverage",
        True,
        "Every target element has one generated set and the expected material section.",
    )

    remainder_name = assignment.get("remainder_set")
    if remainder_name is not None:
        expected_remainder = int(region["section_remainder_count"])
        remainder_set = _repository_item(part.sets, remainder_name, "Section remainder set")
        actual_remainder = len(remainder_set.elements)
        _check(
            checks,
            "section_remainder",
            actual_remainder == expected_remainder,
            f"Imported section remainder count: {actual_remainder}",
        )


def _run_job(model_name, mode, requested_name, work_directory, checks):
    if mode == "import":
        return None
    work_directory.mkdir(parents=True, exist_ok=True)
    os.chdir(str(work_directory))
    default_name = "RFM_{}_{}".format(
        mode,
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
    )
    job_name = requested_name or default_name
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", job_name):
        raise RuntimeError("Abaqus job name must contain only letters, digits, and underscores.")
    job = mdb.Job(name=job_name, model=model_name, type=ANALYSIS)
    if mode == "datacheck":
        job.submit(consistencyChecking=OFF, datacheckJob=True)
    else:
        job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    status = str(job.status)
    accepted = (
        status in ("CHECK_COMPLETED", "COMPLETED") if mode == "datacheck" else status == "COMPLETED"
    )
    _check(
        checks,
        f"abaqus_{mode}",
        accepted,
        f"Abaqus job {job_name} ended with status {status}.",
    )
    return job_name


def _about():
    try:
        return dict(session.about())
    except Exception:
        return {"description": "Abaqus session metadata was unavailable."}


def main():
    arguments = _arguments()
    input_path = arguments.input.expanduser().resolve()
    manifest_path = arguments.manifest.expanduser().resolve()
    report_path = arguments.report.expanduser().resolve()
    work_directory = (
        arguments.work_directory.expanduser().resolve()
        if arguments.work_directory is not None
        else report_path.parent / "abaqus-jobs"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = []
    artifacts = {
        "generated_input": _sha256(input_path),
        "rfieldmesh_manifest": _sha256(manifest_path),
    }
    status = "failed"
    notes = []
    try:
        expected_output_hash = manifest["output"]["sha256"]
        _check(
            checks,
            "input_checksum",
            artifacts["generated_input"] == expected_output_hash,
            "Generated input checksum matches the RFieldMesh manifest.",
        )
        model_name = "RFieldMeshNativeValidation"
        if model_name in mdb.models:
            del mdb.models[model_name]
        model = mdb.ModelFromInputFile(name=model_name, inputFileName=str(input_path))
        _check(checks, "abaqus_import", True, "Abaqus/CAE imported the input without error.")
        _validate_import(model, manifest, arguments.relative_tolerance, checks)
        job_name = _run_job(
            model_name,
            arguments.mode,
            arguments.job_name,
            work_directory,
            checks,
        )
        if job_name is not None:
            for suffix in (".dat", ".msg", ".sta", ".odb"):
                candidate = work_directory / (job_name + suffix)
                if candidate.is_file():
                    artifacts[f"abaqus_job{suffix}"] = _sha256(candidate)
        status = "passed"
    except Exception as exc:
        checks.append(
            {
                "check_id": "native_validation_exception",
                "passed": False,
                "details": f"{type(exc).__name__}: {exc}",
            }
        )
        notes.append(traceback.format_exc())

    report = {
        "schema_version": "1.0",
        "gate_id": arguments.gate_id,
        "status": status,
        "application_version": manifest["application_version"],
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version,
            "platform": sys.platform,
            "abaqus": _about(),
            "mode": arguments.mode,
        },
        "checks": checks,
        "artifacts": artifacts,
        "notes": notes,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
