param(
    [string]$Python = "py -3.12",
    [string]$OutputDirectory = "release-windows"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

$Venv = Join-Path $ProjectRoot ".venv-windows-build"
if (-not (Test-Path $Venv)) {
    Invoke-Native -Description "Virtual-environment creation" -Command {
        Invoke-Expression "$Python -m venv `"$Venv`""
    }
}

$PythonExe = Join-Path $Venv "Scripts\python.exe"
Invoke-Native -Description "pip bootstrap" -Command {
    & $PythonExe -m pip install --upgrade pip "uv==0.11.29"
}
$UvExe = Join-Path $Venv "Scripts\uv.exe"
$ReleaseRoot = Join-Path $ProjectRoot $OutputDirectory
$EvidenceDirectory = Join-Path $ReleaseRoot "evidence"
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null
$LockedRequirements = Join-Path $EvidenceDirectory "locked-requirements.txt"
Invoke-Native -Description "Frozen dependency export" -Command {
    & $UvExe export `
        --frozen `
        --all-extras `
        --no-emit-project `
        --format requirements-txt `
        --output-file $LockedRequirements
}
Invoke-Native -Description "Locked dependency installation" -Command {
    & $PythonExe -m pip install --require-hashes --requirement $LockedRequirements
}
Invoke-Native -Description "Candidate source installation" -Command {
    & $PythonExe -m pip install --no-deps --editable .
}

$JunitReport = Join-Path $EvidenceDirectory "pytest-junit.xml"
$CoverageReport = Join-Path $EvidenceDirectory "coverage.json"
Invoke-Native -Description "Test suite" -Command {
    & $PythonExe -m pytest --junitxml $JunitReport `
        --cov=rfieldmesh --cov-report=term-missing --cov-report="json:$CoverageReport"
}
Invoke-Native -Description "Ruff linting" -Command { & $PythonExe -m ruff check . }
Invoke-Native -Description "Ruff formatting" -Command { & $PythonExe -m ruff format --check . }
Invoke-Native -Description "Strict type checking" -Command { & $PythonExe -m mypy src }

$PythonDistributions = Join-Path $ReleaseRoot "python-distributions"
New-Item -ItemType Directory -Path $PythonDistributions -Force | Out-Null
Invoke-Native -Description "Python package build" -Command {
    & $PythonExe -m build --outdir $PythonDistributions
}

$DistDirectory = Join-Path $ReleaseRoot "dist"
$WorkDirectory = Join-Path $ReleaseRoot "build"
$SpecPath = Join-Path $ProjectRoot "packaging\pyinstaller\rfieldmesh-gui.spec"
Invoke-Native -Description "PyInstaller build" -Command {
    & $PythonExe -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $DistDirectory `
        --workpath $WorkDirectory `
        $SpecPath
}

$AppDirectory = Join-Path $DistDirectory "RFieldMesh"
$Executable = Join-Path $AppDirectory "RFieldMesh.exe"
if (-not (Test-Path $Executable)) {
    throw "PyInstaller did not produce RFieldMesh.exe."
}

$SmokeScript = Join-Path $ProjectRoot "packaging\windows\smoke_test.ps1"
& $SmokeScript `
    -PythonExe $PythonExe `
    -Executable $Executable `
    -EvidenceDirectory $EvidenceDirectory

$LicenceDirectory = Join-Path $AppDirectory "licences"
New-Item -ItemType Directory -Path $LicenceDirectory -Force | Out-Null
Copy-Item "LICENSE" (Join-Path $AppDirectory "LICENSE.txt") -Force
Copy-Item "packaging\licences\THIRD_PARTY_NOTICES.md" `
    (Join-Path $LicenceDirectory "THIRD_PARTY_NOTICES.md") -Force
$LicenceInventory = Join-Path $LicenceDirectory "PYTHON_PACKAGE_LICENCES.txt"
$RawLicenceInventory = Join-Path $EvidenceDirectory "python-package-licences.json"
Invoke-Native -Description "Licence inventory" -Command {
    & $PythonExe -m piplicenses `
        --format=json `
        --with-license-file `
        --output-file $RawLicenceInventory
}
Invoke-Native -Description "Licence inventory sanitization" -Command {
    & $PythonExe "packaging\licences\render_inventory.py" `
        --input $RawLicenceInventory `
        --output $LicenceInventory
}
Copy-Item "packaging\licences\LGPL-3.0.txt" $LicenceDirectory -Force
Copy-Item "packaging\licences\GPL-3.0.txt" $LicenceDirectory -Force
Copy-Item "README.md" $AppDirectory -Force
Copy-Item "RELEASE_NOTES_1.0.0.md" $AppDirectory -Force
Copy-Item "KNOWN_LIMITATIONS.md" $AppDirectory -Force
Copy-Item "CITATION.cff" $AppDirectory -Force
Copy-Item "docs\user_guide\quickstart.md" $AppDirectory -Force

$SourceSmokeReport = Join-Path $EvidenceDirectory "windows_source_gui_smoke.json"
$PackagedSmokeReport = Join-Path $EvidenceDirectory "windows_packaged_gui_smoke.json"
$WindowsEvidence = Join-Path $EvidenceDirectory "windows_build.json"
$EvidenceWriter = Join-Path $ProjectRoot "packaging\windows\write_evidence.py"
$EvidenceArguments = @(
    $EvidenceWriter,
    "--source-report", $SourceSmokeReport,
    "--packaged-report", $PackagedSmokeReport,
    "--executable", $Executable,
    "--licence-inventory", $LicenceInventory,
    "--third-party-notice", (Join-Path $LicenceDirectory "THIRD_PARTY_NOTICES.md"),
    "--gpl-text", (Join-Path $LicenceDirectory "GPL-3.0.txt"),
    "--lgpl-text", (Join-Path $LicenceDirectory "LGPL-3.0.txt"),
    "--output", $WindowsEvidence
)
Invoke-Native -Description "Windows evidence validation" -Command {
    & $PythonExe @EvidenceArguments
}
New-Item -ItemType Directory -Path (Join-Path $AppDirectory "validation") -Force | Out-Null
Copy-Item $WindowsEvidence (Join-Path $AppDirectory "validation\windows_build.json") -Force
Copy-Item "packaging\windows\clean_machine_test.ps1" `
    (Join-Path $AppDirectory "validation\clean_machine_test.ps1") -Force
$AbaqusFixtureDirectory = Join-Path $AppDirectory "validation\abaqus"
New-Item -ItemType Directory -Path $AbaqusFixtureDirectory -Force | Out-Null
Copy-Item "validation\abaqus\small_explicit_source.inp" $AbaqusFixtureDirectory -Force
Copy-Item "validation\abaqus\small_explicit_generation.json" $AbaqusFixtureDirectory -Force
$AbaqusToolsDirectory = Join-Path $AppDirectory "validation\abaqus-tools"
Copy-Item "packaging\abaqus" $AbaqusToolsDirectory -Recurse -Force
$TemplateDirectory = Join-Path $AppDirectory "validation\templates"
Copy-Item "validation\release_candidate\templates" $TemplateDirectory -Recurse -Force

$Version = & $PythonExe -c "import rfieldmesh; print(rfieldmesh.__version__)"
$Archive = Join-Path $ReleaseRoot "RFieldMesh-$Version-windows-x64.zip"
if (Test-Path $Archive) {
    Remove-Item $Archive -Force
}
Compress-Archive -Path $AppDirectory -DestinationPath $Archive -CompressionLevel Optimal
$Hash = (Get-FileHash -Algorithm SHA256 $Archive).Hash.ToLowerInvariant()
$ChecksumFile = "$Archive.sha256"
"$Hash  $([System.IO.Path]::GetFileName($Archive))" | Set-Content `
    -Path $ChecksumFile `
    -Encoding ascii
Write-Host "Windows release: $Archive"
Write-Host "SHA-256: $Hash"
