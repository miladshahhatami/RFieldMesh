param(
    [Parameter(Mandatory = $true)]
    [string]$InputFile,
    [Parameter(Mandatory = $true)]
    [string]$Manifest,
    [Parameter(Mandatory = $true)]
    [ValidateSet("abaqus_import_2d", "abaqus_import_3d", "abaqus_explicit_analysis")]
    [string]$GateId,
    [Parameter(Mandatory = $true)]
    [ValidateSet("import", "datacheck", "analysis")]
    [string]$Mode,
    [string]$ReportDirectory = "validation\release_candidate\evidence",
    [string]$AbaqusCommand = "abaqus",
    [string]$JobName = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$InputPath = (Resolve-Path $InputFile).Path
$ManifestPath = (Resolve-Path $Manifest).Path
$EvidenceDirectory = Join-Path $ProjectRoot $ReportDirectory
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
$ReportPath = Join-Path $EvidenceDirectory "$GateId.json"
$WorkDirectory = Join-Path $EvidenceDirectory "abaqus-jobs"
$ValidationScript = Join-Path $PSScriptRoot "validate_generated_model.py"

$Arguments = @(
    "cae",
    "noGUI=$ValidationScript",
    "--",
    "--input", $InputPath,
    "--manifest", $ManifestPath,
    "--report", $ReportPath,
    "--gate-id", $GateId,
    "--mode", $Mode,
    "--work-directory", $WorkDirectory
)
if ($JobName) {
    $Arguments += @("--job-name", $JobName)
}

& $AbaqusCommand @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "Abaqus native validation failed for gate $GateId."
}
Write-Host "Abaqus evidence: $ReportPath"
