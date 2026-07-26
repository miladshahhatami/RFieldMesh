param(
    [string]$ApplicationDirectory = "",
    [string]$Output = "windows_clean_machine.json"
)

$ErrorActionPreference = "Stop"
if (-not $ApplicationDirectory) {
    $ApplicationDirectory = Join-Path $PSScriptRoot ".."
}
$AppDirectory = (Resolve-Path $ApplicationDirectory).Path
$Executable = Join-Path $AppDirectory "RFieldMesh.exe"
if (-not (Test-Path $Executable)) {
    throw "RFieldMesh.exe was not found in $AppDirectory."
}

$OutputPath = [System.IO.Path]::GetFullPath($Output)
$SmokeReport = Join-Path ([System.IO.Path]::GetDirectoryName($OutputPath)) `
    "windows_clean_machine_smoke.json"
$PythonCommands = @()
foreach ($Name in @("python", "python3", "py")) {
    $Resolved = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue
    if ($null -ne $Resolved) {
        $PythonCommands += $Resolved.Source
    }
}

$env:QT_QPA_PLATFORM = "offscreen"
$env:QTWEBENGINE_DISABLE_SANDBOX = "1"
$env:RFIELDMESH_SMOKE_TEST = "1"
$env:RFIELDMESH_SMOKE_REPORT = $SmokeReport
$Process = Start-Process -FilePath $Executable -PassThru
$TimedOut = -not $Process.WaitForExit(30000)
if ($TimedOut) {
    Stop-Process -Id $Process.Id -Force
}

$Smoke = $null
if (Test-Path $SmokeReport) {
    $Smoke = Get-Content $SmokeReport -Raw | ConvertFrom-Json
}
$NormalExit = -not $TimedOut -and $Process.ExitCode -eq 0
$Frozen = $null -ne $Smoke -and $Smoke.frozen
$FiveTabs = $null -ne $Smoke -and $Smoke.tab_count -eq 5
$NoPython = $PythonCommands.Count -eq 0
$Checks = @(
    @{
        check_id = "external_python_absent"
        passed = $NoPython
        details = if ($NoPython) {
            "No python, python3, or py executable was available to the test account."
        } else {
            "External Python commands were found: $($PythonCommands -join ', ')"
        }
    },
    @{
        check_id = "packaged_gui_normal_exit"
        passed = $NormalExit
        details = if ($NormalExit) {
            "The packaged GUI constructed and exited normally through the smoke path."
        } else {
            "The packaged GUI timed out or returned a nonzero exit status."
        }
    },
    @{
        check_id = "embedded_python_runtime"
        passed = $Frozen
        details = if ($Frozen) {
            "The GUI reported a frozen embedded runtime."
        } else {
            "The GUI did not report a frozen embedded runtime."
        }
    },
    @{
        check_id = "five_tab_workflow"
        passed = $FiveTabs
        details = if ($FiveTabs) {
            "All five workflow tabs constructed on the clean machine."
        } else {
            "The expected five-tab workflow was not observed."
        }
    }
)
$Passed = ($Checks | Where-Object { -not $_.passed }).Count -eq 0
$Artifacts = @{
    "RFieldMesh.exe" = (Get-FileHash -Algorithm SHA256 $Executable).Hash.ToLowerInvariant()
}
$Report = @{
    schema_version = "1.0"
    gate_id = "windows_clean_machine"
    status = if ($Passed) { "passed" } else { "failed" }
    application_version = if ($null -ne $Smoke) { $Smoke.application_version } else { "unknown" }
    executed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    environment = @{
        operating_system = [System.Environment]::OSVersion.VersionString
        powershell = $PSVersionTable.PSVersion.ToString()
        external_python_commands = $PythonCommands
    }
    checks = $Checks
    artifacts = $Artifacts
    notes = @(
        "Run the separate user-acceptance protocol after this automated clean-machine gate."
    )
}
$Parent = [System.IO.Path]::GetDirectoryName($OutputPath)
New-Item -ItemType Directory -Path $Parent -Force | Out-Null
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    $OutputPath,
    ($Report | ConvertTo-Json -Depth 8),
    $Utf8NoBom
)
Write-Host "Clean-machine evidence: $OutputPath"
if (-not $Passed) {
    throw "The clean-machine release gate failed."
}
