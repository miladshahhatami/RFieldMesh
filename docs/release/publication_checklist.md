# Public-release checklist

## Repository

- Review author and contact metadata.
- Confirm that no private Abaqus model, credential, personal path, cache,
  virtual environment, or proprietary file is tracked.
- Create and protect the `main` branch.
- Push the exact verified source and tag it `v1.0.0`.
- Run the source-quality and Windows workflows on that tag.

## Python package index

- Inspect the wheel and source distribution contents.
- Install the wheel into a clean environment and run CLI smoke checks.
- Upload first to TestPyPI if the project name and metadata have not been
  exercised previously.
- Configure PyPI trusted publishing or use a short-lived scoped token.
- Publish the exact locally verified `1.0.0` wheel and source distribution.
- Verify the published hash and installation command.

## Windows package

- Build from the exact `v1.0.0` tag on Windows.
- Repeat source and frozen-GUI smoke tests.
- Repeat the no-Python clean-machine test.
- Do not rename the `0.9.0rc1` archive as `1.0.0`.
- Publish the ZIP and adjacent SHA-256 file.
- If signing or an installer is introduced, document the certificate and
  installer technology separately.

## Archival DOI

- Connect the repository to Zenodo or another research-software archive.
- Archive the `v1.0.0` release.
- Add the assigned DOI to `CITATION.cff` in the next documentation patch; do
  not invent a DOI before assignment.
- Archive release notes, source distributions, Windows checksum, validation
  summary, licence, and citation metadata.

## Manuscript

- Report version `1.0.0`, seeds, correlation convention, observation mapping,
  marginal moments, and the mesh applicability boundary.
- Include the limitation paragraph in
  `docs/publication/manuscript_limitations.md`.
- Cite the archived DOI once available.
