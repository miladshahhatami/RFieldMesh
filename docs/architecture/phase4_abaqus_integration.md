# Phase 4 Abaqus integration

## Scope

Phase 4 connects the validated numerical core to Abaqus keyword models without
placing parser or numerical logic in a user interface. It provides:

- byte-preserving source inspection;
- token and semantic parsing;
- part, instance, set, section, and material resolution;
- first-order continuum-element eligibility;
- part-to-assembly coordinate transforms;
- region-local representative coordinates;
- automatic spectral or covariance/KL field generation;
- complete source-material cloning;
- portable per-element material and section assignment;
- section-remainder handling for partial or mixed-type selections;
- atomic output writing;
- output checksum manifests;
- independent post-write reparsing and validation;
- `inspect` and `generate` command-line workflows.

## Eligibility

The stable supported-element registry contains:

`CPE3`, `CPE4`, `CPE4R`, `CPS3`, `CPS4`, `CPS4R`, `CAX3`, `CAX4`,
`CAX4R`, `C3D4`, `C3D8`, and `C3D8R`.

Unsupported elements are excluded explicitly and reported by type. They are
not deleted. If they share the original section with randomized elements, the
writer creates a remainder set and redirects the original section to it.

## Coordinate and observation conventions

Element representative points are the mean of the corner-node coordinates,
which is the isoparametric centre for supported linear elements. Instance
translation and axis-angle rotation are applied before the region origin is
subtracted.

With `algorithm="auto"`:

- a complete axis-aligned two-dimensional quadrilateral grid with exponential
  correlation uses the spectral method;
- other eligible regions use covariance/KL.

With `mapping="auto"`:

- a structured spectral field uses analytical rectangular Gaussian averaging;
- covariance/KL uses representative-point sampling.

This default avoids retaining irrelevant high-frequency spectral modes after
element averaging while preserving centroid sampling for general meshes.

## Writer invariants

The Phase 4 writer enforces the following conditions before mutation:

1. the source checksum still matches the inspected file;
2. every eligible target has exactly one source solid section;
3. the region inherits one original material;
4. the source `*Elastic` and `*Density` cards are compatible with the supported
   scalar forms;
5. property values are positive, finite, and cover the eligible labels exactly;
6. generated names do not collide case-insensitively;
7. patches are nonoverlapping;
8. the destination is different from the source.

The complete original material block is cloned for each target element.
Only the first Young's-modulus or density value is replaced; Poisson's ratio,
damping, plasticity, and other material cards remain textually unchanged.

The output is written to a temporary file in the destination directory,
flushed and synchronized, and then published by atomic replacement.

## Known Phase 4 limitations

- Included-file rewriting is prohibited.
- A region must inherit one original material and section.
- Repeated or recursively referenced element-set definitions are not yet
  resolved.
- Only scalar, one-row density and isotropic elasticity are modified.
- Temperature dependence, field-variable dependence, engineering constants,
  and multiline material tables are rejected.
- Instance-level independent fields for repeated instances remain deferred.
- `AC3D8R` is inspected but remains ineligible.
- Distribution/table-based Abaqus property assignment is not enabled.
