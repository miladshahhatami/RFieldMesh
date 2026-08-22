"""Model-inspection application service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rfieldmesh.abaqus.element_registry import element_descriptor
from rfieldmesh.abaqus.parser import parse_abaqus_model


def inspect_model(path: str | Path) -> dict[str, Any]:
    """Return a deterministic JSON-compatible summary of an Abaqus input file."""
    model = parse_abaqus_model(path)
    parts: list[dict[str, Any]] = []
    for part in model.parts.values():
        counts: dict[str, int] = {}
        for element in part.elements.values():
            counts[element.element_type] = counts.get(element.element_type, 0) + 1
        parts.append(
            {
                "name": part.name,
                "node_count": len(part.node_coordinates),
                "element_count": len(part.elements),
                "element_types": dict(sorted(counts.items())),
                "supported_element_count": sum(
                    count
                    for element_type, count in counts.items()
                    if element_descriptor(element_type).supported
                ),
                "element_sets": {
                    element_set.name: len(element_set.labels)
                    for element_set in part.element_sets.values()
                },
                "sections": [
                    {
                        "elset": section.elset_name,
                        "material": section.material_name,
                    }
                    for section in part.sections
                ],
            }
        )
    return {
        "source_path": str(model.source.path),
        "source_sha256": model.source.sha256,
        "source_size_bytes": model.source.size_bytes,
        "encoding": model.source.encoding,
        "newline": "CRLF" if model.source.newline == "\r\n" else "LF",
        "keyword_count": len(model.tokens),
        "parts": parts,
        "instances": [
            {
                "name": instance.name,
                "part": instance.part_name,
                "transformation": instance.transform.matrix.tolist(),
            }
            for instance in model.instances.values()
        ],
        "materials": [
            {
                "name": material.name,
                "density": material.density,
                "youngs_modulus": material.youngs_modulus,
                "elastic_modulus": material.youngs_modulus,
                "poissons_ratio": material.poissons_ratio,
                "friction_angle": material.friction_angle,
                "dilation_angle": material.dilation_angle,
                "cohesion": material.cohesion,
            }
            for material in model.materials.values()
        ],
        "include_paths": [str(path) for path in model.include_paths],
    }
