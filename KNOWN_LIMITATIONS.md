# Known limitations in RFieldMesh 1.0.0

This document defines the applicability boundary of the stable release. A model
outside this boundary is not necessarily invalid; it requires a numerical or
writing capability that is not implemented in version 1.0.0.

## Random-field generation

The general-coordinate algorithm forms a dense covariance matrix and computes a
Karhunen–Loève eigendecomposition. Its memory requirement is \(O(N^2)\), and a
full dense eigendecomposition has approximately \(O(N^3)\) computational
complexity. A method-specific safeguard therefore limits this route to
moderate-sized regions. Removing the safeguard does not make the calculation
scalable and may exhaust system memory.

The Fourier spectral route is scalable but currently requires all of the
following:

- a two-dimensional region;
- first-order quadrilateral continuum elements;
- a complete structured grid;
- rectangular elements aligned with the global coordinate axes;
- exponential correlation for the implemented analytical spectrum.

Large rotated, skewed, incomplete, or unstructured meshes therefore have no
supported scalable route in version 1.0.0. Independent subdivision of one
physical domain is not an equivalent workaround because it removes
cross-boundary spatial correlation.

Planned work includes rotated-grid recognition and an auxiliary-grid spectral
method with interpolation or element averaging for general meshes. Resource
estimation should then replace any application-wide point-count concept,
although individual algorithms will retain scientifically necessary
safeguards.

## Abaqus model scope

- Generation is refused when `*INCLUDE` is present. Included content may still
  be inspected.
- Supported elements are first-order continuum elements listed in the README.
  Unsupported types, including `AC3D8R`, are reported and preserved under their
  original assignment where section-remainder handling applies.
- A configured region must inherit one unambiguous original solid section.
- Only scalar, one-row `*Density` and isotropic, one-row `*Elastic` properties
  are modified.
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
