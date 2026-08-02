# Phase 7 stable-release record

RFieldMesh 1.0.0 was promoted from `0.9.0rc1` after the user confirmed the
three outstanding native checks: supported-model generation and Abaqus use,
clean Windows packaged-application operation, and completion of the requested
native validation sequence.

The scientific core was frozen during the original promotion. Before public
release or manuscript submission, coauthor-requested five-property and
large-mesh enhancements were incorporated while retaining version 1.0.0. The
updated source requires a new Windows package and native Abaqus confirmation;
earlier native evidence applies only to its recorded source state.

## Deferred scope

The stable release does not claim unlimited processing of general meshes.
Dense KL has a memory safeguard, while larger general meshes use a matrix-free
low-rank covariance factor with explicit mode and memory budgets. The scalable
spectral mapper requires a complete, axis-aligned, structured 2D quadrilateral
grid. No fixed point-count cap is applied.

## Promotion rule

Source version 1.0.0 is suitable for stable source distribution after all local
tests, linting, formatting, typing, package builds, clean-wheel installation,
archive-integrity checks, and release-document consistency checks pass.

A public Windows binary labelled 1.0.0 must be rebuilt from the tagged 1.0.0
source on Windows. A prior `0.9.0rc1` executable must not be renamed. GitHub,
PyPI, Zenodo, code signing, and installer publication require maintainer-owned
accounts and are separate external publication actions.
