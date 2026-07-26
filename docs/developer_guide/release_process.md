# Release process

RFieldMesh uses Semantic Versioning. Numerical semantics, RNG conventions,
supported Abaqus syntax, or output interpretation require an explicit
compatibility assessment before release.

1. Update the version, changelog, release notes, citation metadata, lock file,
   and stable templates.
2. Run the complete source suite, coverage, lint, formatting, strict typing,
   Phase 3–6 regression scripts, and Phase 7 release-asset validation.
3. Build the wheel and source distribution.
4. Install the wheel in a clean environment and run `rfieldmesh --help`,
   `rfieldmesh inspect --help`, and `rfieldmesh release-audit --help`.
5. Inspect archives for private files, absolute personal paths, caches, and
   virtual environments.
6. Build the same version on native Windows and perform clean-machine checks.
7. Repeat Abaqus-native validation whenever executable code, generated input
   syntax, dependency versions, or packaging contents relevant to the workflow
   change.
8. Tag and publish only the exact verified source state.

Missing native evidence is never converted to success by a source-only test.
User attestation may document a project decision, but it must remain labelled
as attestation rather than machine evidence.
