# Phase 8 publication record

This record separates locally verified release preparation from external
publication actions that require the maintainer's accounts.

## Prepared and verified

- Stable source version: `1.0.0`.
- GitHub community files and continuous-integration workflows.
- `CITATION.cff` and `.zenodo.json` citation/deposition metadata.
- SoftwareX manuscript draft, highlights, and graphical abstract.
- Six-property source, representative 2D/3D outputs, and scalable
  general-coordinate validation completed after coauthor review.
- Large-mesh resource boundaries disclosed in user and manuscript documentation.
- Native release-candidate validation retained as user attestation; no
  substitute logs were manufactured.

## External actions pending

- Create or authorize the public GitHub repository and push the exact verified
  source.
- Rebuild and upload `RFieldMesh-1.0.0-windows-x64.zip` from the tagged stable
  source. The prior `0.9.0rc1` binary must not be renamed.
- Create the `v1.0.0` GitHub release and attach the distributions, Windows
  archive, checksum files, release notes, and validation summary.
- Enable the repository in Zenodo and archive the GitHub release.
- Insert the assigned DOI and final repository URL into the citation metadata
  and manuscript in a documentation-only patch.

The source bundle is ready for maintainer review. Updated distributions and the
Windows package must be rebuilt from this exact source before publication; the
bundle is not evidence that a public repository or DOI already exists.
