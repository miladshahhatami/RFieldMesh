# Native Abaqus validation

Release validation requires Abaqus itself to import generated models. Internal RFieldMesh
reparsing is a separate safety layer and does not satisfy this native gate.

The validator uses only the Python standard library and Abaqus/CAE modules. Run
it from a Windows PowerShell session where the `abaqus` command is available.

## 1. Generate the three validation outputs

Copy the two JSON templates under
`validation\release_candidate\templates`, replace their private input and
output paths, and generate each case:

```powershell
rfieldmesh generate C:\validation\abaqus_2d_generation.json
rfieldmesh generate C:\validation\abaqus_3d_generation.json
```

Retain each `.rfieldmesh.json` manifest. Generate the redistributable smoke
model with:

```powershell
rfieldmesh generate validation\abaqus\small_explicit_generation.json
```

## 2. Import the realistic generated models

```powershell
.\packaging\abaqus\validate.ps1 `
  -InputFile C:\validation\generated_2d.inp `
  -Manifest C:\validation\generated_2d.rfieldmesh.json `
  -GateId abaqus_import_2d `
  -Mode import

.\packaging\abaqus\validate.ps1 `
  -InputFile C:\validation\generated_3d.inp `
  -Manifest C:\validation\generated_3d.rfieldmesh.json `
  -GateId abaqus_import_3d `
  -Mode import
```

## 3. Execute the small Abaqus/Explicit analysis

```powershell
.\packaging\abaqus\validate.ps1 `
  -InputFile validation\abaqus\output\small_explicit_generated.inp `
  -Manifest validation\abaqus\output\small_explicit_generated.rfieldmesh.json `
  -GateId abaqus_explicit_analysis `
  -Mode analysis `
  -JobName RFM_Stable_Smoke
```

The validator checks the generated-file checksum, native model import,
element-set and section coverage, imported Young's-modulus and density values,
section-remainder membership where applicable, and native job completion. It
writes versioned evidence under `validation\release_candidate\evidence`.

Do not edit a passing evidence file. If a defect is corrected or the
application version changes, regenerate every affected native report.
