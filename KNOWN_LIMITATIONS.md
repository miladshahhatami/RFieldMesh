# Known limitations in RFieldMesh 1.0.0

This document defines the applicability boundary of the stable release. A model
outside this boundary is not necessarily invalid; it requires a numerical or
writing capability that is not implemented in version 1.0.0.

## Random-field generation

The general-coordinate algorithm estimates dense covariance and eigensolver
workspace before allocation. It uses dense Karhunen–Loève decomposition only
within the configured memory budget; otherwise it constructs a matrix-free
pivoted covariance factor. The latter stores \(O(Nr)\) values and evaluates
covariance columns in blocks. Its residual-trace stopping rule retains the
configured fraction of total point variance.

The dense path still has quadratic \(O(N^2)\) covariance storage and an
approximately cubic full eigendecomposition; the automatic estimate prevents
that path from being selected outside its configured resource budget.

There is no fixed element-count or point-count rejection. Nevertheless,
computation is not unlimited. A weakly correlated field may require a large
rank \(r\), and the calculation stops with a resource error if the requested
variance cannot be reached within the configured mode and memory budgets. The
legacy `max_points` JSON field is accepted for compatibility but is not used as
an execution limit.

The Fourier spectral route is scalable but currently requires all of the
following:

- a two-dimensional region;
- first-order quadrilateral continuum elements;
- a complete structured grid;
- rectangular elements aligned with the global coordinate axes;
- exponential correlation for the implemented analytical spectrum.

For bounded centroid-sampled fields on a supported structured mesh,
`algorithm=auto` retries an otherwise infeasible spectral request at `0.995`
retained variance per direction. The combined retained point variance is then
approximately `0.990` or greater, and the adjustment is recorded in field and
manifest diagnostics. This fallback does not apply when `algorithm=spectral`
is selected explicitly. It also does not remove the coefficient-memory limit;
an adjusted request that remains too large still fails before field allocation.

Rotated, skewed, incomplete, and unstructured meshes use the scalable
general-coordinate route. Independent subdivision of one physical domain is
not an equivalent workaround because it removes cross-boundary spatial
correlation.

Planned work includes rotated-grid recognition and an auxiliary-grid spectral
method with interpolation or element averaging for general meshes. Individual
algorithms will continue to retain scientifically necessary memory and
accuracy safeguards.

## Abaqus model scope

- Generation is refused when `*INCLUDE` is present. Included content may still
  be inspected.
- Supported elements are first-order continuum elements listed in the README.
  Unsupported types, including `AC3D8R`, are reported and preserved under their
  original assignment where section-remainder handling applies.
- A configured region must inherit one unambiguous original solid section.
- Only scalar, one-row `*Density`, isotropic `*Elastic`, `*Mohr Coulomb`, and
  `*Mohr Coulomb Hardening` rows without temperature, field, or dependency
  parameters are modified. For hardening, cohesion is the first value and all
  companion columns are preserved.
- The supported random variables are Young's modulus, density, Poisson's ratio,
  friction angle, dilation angle, and cohesion. RFieldMesh does not introduce
  `*Mohr Coulomb` or `*Mohr Coulomb Hardening` into a material that lacks the
  required keyword.
- Cohesion must be nonnegative. Generated negative values are rejected rather
  than clipped; truncated normal with a lower bound of zero is the default.
- The constitutive recommendation that dilation angle should generally not
  exceed friction angle is not silently enforced; users must define physically
  defensible joint bounds and review the generated fields.
- Independent fields for repeated instances of the same part are deferred.
- Abaqus distribution-based assignment is not used in this release.

## Observation mapping and execution

- Analytical local averaging is implemented for axis-aligned rectangular
  two-dimensional elements.
- General unstructured area or volume averaging is not implemented; the KL
  route samples representative points.
- Batch generation is sequential, with cooperative cancellation between
  realizations.
- Windows packaging produces an unsigned one-folder ZIP rather than a signed
  installer.

These limitations should be reported when they materially affect a published
analysis.
