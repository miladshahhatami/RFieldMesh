# Public-release checklist

Status legend: **prepared** means verified locally; **pending maintainer
action** requires an authorized external account or the stable Windows
artifact.

## Repository

- **Prepared:** Review author metadata.
- **Prepared:** Confirm that no private Abaqus model, credential, personal path, cache,
  virtual environment, or proprietary file is tracked.
- **Pending maintainer action:** Create and protect the `main` branch.
- **Pending maintainer action:** Push the exact verified source and tag it `v1.0.0`.
- **Pending maintainer action:** Run the source-quality and Windows workflows on that tag.

## Python package index

- **Prepared:** Inspect the wheel and source distribution contents.
- **Prepared:** Install the wheel into a clean environment and run CLI smoke checks.
- Upload first to TestPyPI if the project name and metadata have not been
  exercised previously.
- Configure PyPI trusted publishing or use a short-lived scoped token.
- Publish the exact locally verified `1.0.0` wheel and source distribution.
- Verify the published hash and installation command.

## Windows package

- **Pending maintainer action:** Build from the exact `v1.0.0` tag on Windows.
- Repeat source and frozen-GUI smoke tests.
- Repeat the no-Python clean-machine test.
- Do not rename the `0.9.0rc1` archive as `1.0.0`.
- Publish the ZIP and adjacent SHA-256 file.
- If signing or an installer is introduced, document the certificate and
  installer technology separately.

## Archival DOI

- **Pending maintainer action:** Connect the repository to Zenodo or another research-software archive.
- **Pending maintainer action:** Archive the `v1.0.0` release.
- Add the assigned DOI to `CITATION.cff` in the next documentation patch; do
  not invent a DOI before assignment.
- Archive release notes, source distributions, Windows checksum, validation
  summary, licence, and citation metadata.

## Manuscript

- **Prepared:** Report version `1.0.0`, seeds, correlation convention, observation mapping,
  marginal moments, and the mesh applicability boundary.
- **Prepared:** Include the limitation paragraph in
  `docs/publication/manuscript_limitations.md`.
- **Pending maintainer action:** Cite the archived DOI once available.
