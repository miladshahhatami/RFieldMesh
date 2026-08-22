# RFieldMesh 1.0.0 — pre-submission release

RFieldMesh 1.0.0 generates independent, reproducible random fields for six
Abaqus material properties: Young's modulus, density, Poisson's ratio,
friction angle, dilation angle, and cohesion.

## Cohesion support

- `cohesion` is available through the Python API, JSON CLI workflow, GUI,
  previews, diagnostics, batch generation, manifests, writer, and verifier.
- Cohesion is read from and written to the first numerical value in the first
  data row under `*Mohr Coulomb Hardening`.
- The writer clones the full source material, replaces only cohesion, and
  preserves every companion value and unrelated keyword.
- Cohesion is constrained to `c >= 0`; invalid generated values are rejected,
  never clipped. Truncated normal with lower bound zero is the GUI default.
- Cohesion has its own deterministic RNG stream. Existing configurations and
  the five original streams remain backward compatible.
- Missing, dependent, multiline, duplicate, and ambiguous hardening cards are
  rejected before an output model is published.

## Numerical and model scope

The existing spectral, covariance/Karhunen–Loève, mapping, correlation,
marginal, preview, and batch frameworks apply to cohesion without a separate
numerical code path. Supported Abaqus element and material-layout boundaries
are documented in `KNOWN_LIMITATIONS.md`.

Automatic spectral generation now recovers when the default directional
retained-variance target is infeasible for a bounded centroid-sampled field:
it retries at `0.995` per direction, records the requested and effective
targets, and compacts mode-count overshoot. Explicit spectral requests remain
strict, and the application version remains `1.0.0`.

## Native validation status

Source validation and Python distributions can be produced on Linux. A
Windows executable must be built and smoke-tested on native Windows using
`packaging/windows/build.ps1`. Abaqus import, datacheck, and analysis require a
licensed Abaqus installation and are not implied by source-level reparsing.

The application and distribution version remains exactly `1.0.0` because this
coauthor-requested enhancement precedes manuscript submission.
