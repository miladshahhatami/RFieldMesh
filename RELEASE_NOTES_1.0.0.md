# RFieldMesh 1.0.0 — stable release

## Outcome

Version 1.0.0 promotes the validated `0.9.0rc1` scientific core to the first
stable release. No random-field algorithm, Abaqus parsing rule, material-writing
rule, or reproducibility convention was changed during promotion.

## Stable capabilities

- reproducible Gaussian, lognormal, and truncated-normal spatial fields;
- exponential and squared-exponential latent correlation models;
- structured two-dimensional spectral simulation with rectangular local
  averaging;
- covariance/Karhunen–Loève simulation for moderate general-coordinate models;
- safe Abaqus inspection, region resolution, material cloning, section
  assignment, manifest generation, and independent reparsing;
- command-line inspection, preview, generation, batch, and release-audit
  workflows;
- self-contained Plotly visualization;
- five-tab PySide6 desktop application with background execution and
  cooperative cancellation;
- reproducible Windows PyInstaller build assets and native validation
  protocols.

## Validation basis

The source suite covers the numerical core, statistical behavior, MATLAB
regression, Abaqus parsing and writing, desktop presentation state, batch
generation, visualization, packaging, and fail-closed evidence auditing.
Native Phase 6 validation was completed by the user on Windows and Abaqus
before promotion. The stable source archive records that confirmation as a
user attestation; it does not substitute invented machine-generated logs for
evidence files that were not uploaded.

## Applicability boundary

Dense KL generation remains limited to moderate point counts. The scalable
spectral mapper requires a complete, axis-aligned, structured 2D quadrilateral
mesh. Large rotated, skewed, or unstructured meshes are deferred to a later
version. See `KNOWN_LIMITATIONS.md` and
`docs/publication/manuscript_limitations.md`.

## Publication status

This package is ready for repository, package-index, and archival publication.
No external GitHub, PyPI, or Zenodo publication is implied by the presence of
these files. The publication checklist requires the maintainer to review
metadata, rebuild native version `1.0.0` artifacts, publish them through the
maintainer's accounts, and record the resulting URLs and DOI.
