# Changelog

All notable changes follow Semantic Versioning.

## 1.0.0 — Stable release

- Promoted the validated `0.9.0rc1` scientific core without changing numerical
  algorithms or Abaqus-writing semantics.
- Added stable-release notes, a quick-start guide, a publication checklist,
  contribution guidance, security policy, code of conduct, and issue templates.
- Documented the dense KL resource boundary and the structured, axis-aligned
  mesh requirement of the current spectral mapper.
- Added manuscript-ready limitations text and a machine-readable promotion
  record that distinguishes user-attested native validation from uploaded
  machine evidence.
- Updated Windows packaging to distribute the stable release notes, citation
  metadata, quick-start guide, and known-limitations document.
- Added cross-platform source-quality automation for supported Python versions.

## 0.9.0rc1 — Phase 6 release-candidate preparation

- Added versioned evidence contracts and a fail-closed release audit.
- Added reproducible, lock-enforced Windows builds and a separate no-Python
  clean-machine gate with durable smoke evidence.
- Added automatic frozen-GUI startup and shutdown validation.
- Added native Abaqus/CAE import, property, section, datacheck, and analysis validation.
- Added a redistributable two-element Abaqus/Explicit acceptance model.
- Added clean-machine user-acceptance protocol and evidence template.
- Added complete LGPL-3.0 and GPL-3.0 texts and expanded Qt redistribution notices.
- Added exact generated material and element-set provenance to realization manifests.

## 0.3.0a1 — Phase 5 desktop and batch workflows

- Added an unsaved preview application service.
- Added offline interactive Plotly field and distribution reports.
- Added preflighted, cancellable multi-realization batch generation.
- Added batch and preview CLI commands.
- Added a five-tab PySide6 desktop workflow with background workers.
- Added Windows PyInstaller packaging and clean-machine build automation.
- Added desktop, visualization, batch, GUI smoke, and packaging tests.

## 0.2.0a1 — Phase 4 Abaqus integration

- Added byte-preserving Abaqus source inspection and keyword tokenization.
- Added semantic parsing for parts, instances, nodes, elements, sets, sections,
  materials, and include detection.
- Added the accepted first-order continuum-element eligibility registry.
- Added representative-point geometry and instance transformations.
- Added structured-grid recognition and automatic spectral/KL selection.
- Added end-to-end material-field generation for Young's modulus and density.
- Added full source-material cloning and portable per-element assignments.
- Added section-remainder handling for mixed or partial regions.
- Added atomic patch writing, manifests, and independent output reparsing.
- Added `rfieldmesh inspect` and `rfieldmesh generate` commands.
- Added 2D and 3D supplied-model validation.

## 0.1.0a1 — Phase 3 numerical prototype

- Added validated correlation and local-averaging equations.
- Added normal, lognormal, and truncated-normal marginal transformations.
- Added deterministic NumPy `Generator` stream construction.
- Added corrected two-dimensional Fourier spectral simulation.
- Added covariance/Karhunen–Loève simulation for irregular coordinates.
- Added statistical summaries and MATLAB-reference regression tests.
- Added an interactive Phase 3 validation-report generator.
