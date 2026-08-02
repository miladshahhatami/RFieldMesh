# RFieldMesh 1.0.0 publication metadata

## Repository

- **Name:** `RFieldMesh`
- **Description:** Reproducible spatial random fields for finite-element meshes.
- **Visibility:** Public.
- **Topics:** `random-fields`, `finite-element-method`, `geotechnical-engineering`,
  `spatial-variability`, `uncertainty-quantification`, `abaqus`, `python`,
  `pyside6`.
- **Default branch:** `main`.
- **Release tag:** `v1.0.0`.
- **Licence:** BSD-3-Clause.
- **Social preview:** `docs/assets/rfieldmesh-social-preview.png`.

The repository URL must be inserted only after the repository has been created.
No repository owner or URL is inferred in advance.

## GitHub release title

`RFieldMesh 1.0.0`

## GitHub release summary

RFieldMesh 1.0.0 is the first stable release of an independent scientific
application for generating reproducible spatial random fields and assigning
them safely to finite-element models. The release includes a Python API, CLI,
five-tab desktop GUI, offline Plotly reports, deterministic batch generation,
source-preserving Abaqus input-file rewriting, a Windows one-folder package,
and auditable scientific and native validation workflows.

The release supports exponential and squared-exponential latent Gaussian
correlation, normal, lognormal, and moment-fitted truncated-normal marginals,
structured two-dimensional spectral simulation with analytical rectangular
local averaging, and automatic dense KL or matrix-free pivoted covariance
simulation for general meshes.

Large rotated, skewed, incomplete, or unstructured domains use the scalable
general-coordinate factor. Feasibility depends on the requested retained rank,
correlation scales, and configured memory budget, as documented in
`KNOWN_LIMITATIONS.md`.

## Release assets

- `RFieldMesh-1.0.0-windows-x64.zip`
- `RFieldMesh-1.0.0-windows-x64.zip.sha256`
- `rfieldmesh-1.0.0-py3-none-any.whl`
- `rfieldmesh-1.0.0.tar.gz`
- `SHA256SUMS.txt`
- `RELEASE_NOTES_1.0.0.md`

The Windows ZIP and its adjacent checksum must come from the native `1.0.0`
build. The earlier `0.9.0rc1` package must not be renamed or published.

## Zenodo

The repository contains `.zenodo.json`; therefore, Zenodo will use that file
rather than `CITATION.cff` when archiving the GitHub release. After the public
repository is enabled in Zenodo, publication of GitHub release `v1.0.0` should
create the version DOI. The assigned DOI must then be recorded in
`CITATION.cff`, the README, and the manuscript. A DOI must never be predicted
or inserted before assignment.

## Manuscript data and software availability statement

RFieldMesh version 1.0.0, its source code, validation fixtures, documentation,
and release artifacts are openly available under the BSD-3-Clause licence.
The final public repository URL and archived-release DOI will be inserted after
publication. The proprietary Abaqus software is not distributed with
RFieldMesh, and private user models are excluded from the repository.
