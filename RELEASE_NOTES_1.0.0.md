# RFieldMesh 1.0.0 — stable release

## Outcome

Version 1.0.0 is the first stable, pre-publication release. Coauthor review was
incorporated before public release without changing the version identifier.

## Stable capabilities

- reproducible Gaussian, lognormal, and truncated-normal spatial fields;
- exponential and squared-exponential latent correlation models;
- structured two-dimensional spectral simulation with rectangular local
  averaging;
- automatic dense KL or scalable matrix-free pivoted covariance simulation for
  general-coordinate models, with trace-based variance retention;
- independent random fields for Young's modulus, density, Poisson's ratio,
  friction angle, and dilation angle;
- column-aware `*Elastic` and `*Mohr Coulomb` updates with companion-value
  preservation;
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

No fixed element-count cap is imposed. Feasibility remains conditional on the
configured dense and low-rank memory budgets, requested retained variance,
correlation scales, and available computational resources. See
`KNOWN_LIMITATIONS.md` and
`docs/publication/manuscript_limitations.md`.

## Publication status

This package is ready for repository, package-index, and archival publication.
No external GitHub, PyPI, or Zenodo publication is implied by the presence of
these files. The publication checklist requires the maintainer to review
metadata, rebuild native version `1.0.0` artifacts, publish them through the
maintainer's accounts, and record the resulting URLs and DOI.


## Update

- Increased the default iterative covariance mode limit from 2,048 to
  12,000, enabling high-rank covariance approximation for larger
  unstructured three-dimensional meshes when sufficient memory is available.