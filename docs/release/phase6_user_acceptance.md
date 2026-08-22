# Phase 6 user-acceptance protocol

This protocol is a mandatory release gate for RFieldMesh `0.9.0rc1`. Perform it
with the frozen one-folder Windows application on a clean Windows x64 account.
Use a copy of an Abaqus model; never select the only copy of a research model.

Record the operator, Windows version, screen scaling, application archive
SHA-256, Abaqus version used for later native checks, and any antivirus or
endpoint-protection warning.

## Acceptance workflow

1. Extract the complete ZIP to a writable local directory. Confirm that Python
   is not installed or not present on `PATH`. Run
   `validation\clean_machine_test.ps1` and retain its
   passing `windows_clean_machine.json` evidence.
2. Start `RFieldMesh.exe`. Confirm that five tabs are visible, labels are not
   clipped at the active display scaling, and no console window appears.
3. Inspect the redistributable small model
   `validation\abaqus\small_explicit_source.inp`. Confirm that the application
   reports one part, two eligible `CPE4R` elements, one material, and no
   unsupported elements.
4. Enable Young's modulus, density, Poisson's ratio, friction angle, and
   dilation angle, and cohesion. Retain the documented means, choose
   lognormal marginals, and set two positive correlation scales.
5. Generate a preview. Confirm that the application remains responsive, the
   field and distribution views appear, and the reported values are positive
   and finite.
6. Change the seed and regenerate. Confirm that values change. Restore the
   first seed and confirm that the original values return.
7. Generate two realizations to a new empty directory. Confirm that progress
   reaches completion and that each realization has an `.inp` file and a
   `.rfieldmesh.json` manifest.
8. Repeat a deliberately longer batch and select cancellation after the first
   completed realization. Confirm cooperative cancellation without corruption
   of a completed output.
9. Attempt to write over an existing output with overwrite disabled. Confirm
   that the operation is refused with an actionable message.
10. Disconnect the computer from the network and reopen a generated HTML
    preview. Confirm that plots remain interactive.
11. Review the output names, units, target and empirical statistics, excluded
    element counts, and destination paths for clarity.
12. Close and reopen the application. Confirm normal shutdown and startup.

## Acceptance rule

Every item must pass. A workaround, unexplained warning, crash, clipped control,
silent overwrite, missing licence file, or network-dependent preview is a
failure. Correct the defect and repeat the complete protocol with a newly built
candidate.

Copy
`validation\release_candidate\templates\user_acceptance.template.json` to
`validation\release_candidate\evidence\user_acceptance.json`. Replace every
placeholder, set each check result truthfully, and set `status` to `passed`
only when all checks passed. The application version and ZIP checksum must
match the Windows native-build evidence.

The final audit command is:

```powershell
rfieldmesh release-audit validation\release_candidate\evidence `
  --output validation\release_candidate\release_audit.json `
  --require-ready
```
