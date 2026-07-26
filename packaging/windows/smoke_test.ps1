param(
    [Parameter(Mandatory = $true)]
    [string]$PythonExe,
    [Parameter(Mandatory = $true)]
    [string]$Executable,
    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory
)

$ErrorActionPreference = "Stop"
$EvidenceDirectory = [System.IO.Path]::GetFullPath($EvidenceDirectory)
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
$SourceReport = Join-Path $EvidenceDirectory "windows_source_gui_smoke.json"
$PackagedReport = Join-Path $EvidenceDirectory "windows_packaged_gui_smoke.json"

$env:QT_QPA_PLATFORM = "offscreen"
$env:QTWEBENGINE_DISABLE_SANDBOX = "1"
$env:RFIELDMESH_SMOKE_TEST = "1"

$env:RFIELDMESH_SMOKE_REPORT = $SourceReport
& $PythonExe -m rfieldmesh.gui.application
if ($LASTEXITCODE -ne 0) {
    throw "Source GUI smoke test failed with code $LASTEXITCODE."
}

$env:RFIELDMESH_SMOKE_REPORT = $PackagedReport
$Process = Start-Process -FilePath $Executable -PassThru
if (-not $Process.WaitForExit(30000)) {
    Stop-Process -Id $Process.Id -Force
    throw "Packaged GUI did not exit through its smoke-test path within 30 seconds."
}
if ($Process.ExitCode -ne 0) {
    throw "Packaged GUI smoke test failed with code $($Process.ExitCode)."
}
if (-not (Test-Path $SourceReport) -or -not (Test-Path $PackagedReport)) {
    throw "One or more GUI smoke reports were not created."
}

$Source = Get-Content $SourceReport -Raw | ConvertFrom-Json
$Packaged = Get-Content $PackagedReport -Raw | ConvertFrom-Json
if ($Source.tab_count -ne 5 -or $Source.frozen) {
    throw "Source GUI smoke evidence is inconsistent."
}
if ($Packaged.tab_count -ne 5 -or -not $Packaged.frozen) {
    throw "Packaged GUI smoke evidence is inconsistent."
}
Write-Host "Source and packaged GUI smoke tests passed."
