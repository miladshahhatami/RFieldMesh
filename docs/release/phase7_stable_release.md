# Phase 7 stable-release record

RFieldMesh 1.0.0 was promoted from `0.9.0rc1` after the user confirmed the
three outstanding native checks: supported-model generation and Abaqus use,
clean Windows packaged-application operation, and completion of the requested
native validation sequence.

The scientific core was frozen during promotion. Version, documentation,
packaging contents, public-project metadata, and release automation were
updated. Because the native JSON evidence and Windows ZIP were not uploaded to
the development workspace, the release record describes those checks as
user-attested rather than manufacturing substitute evidence.

## Deferred scope

The stable release does not process arbitrarily large general meshes. Dense KL
has a method-specific resource safeguard, while the scalable spectral mapper
requires a complete, axis-aligned, structured 2D quadrilateral grid. Large
rotated, skewed, or unstructured meshes are explicitly deferred to a later
minor release.

## Promotion rule

Source version 1.0.0 is suitable for stable source distribution after all local
tests, linting, formatting, typing, package builds, clean-wheel installation,
archive-integrity checks, and release-document consistency checks pass.

A public Windows binary labelled 1.0.0 must be rebuilt from the tagged 1.0.0
source on Windows. A prior `0.9.0rc1` executable must not be renamed. GitHub,
PyPI, Zenodo, code signing, and installer publication require maintainer-owned
accounts and are separate external publication actions.
