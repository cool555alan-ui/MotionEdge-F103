[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:Failures = 0

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    if ($Passed) {
        Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green
    }
    else {
        ++$script:Failures
        Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red
    }
}

function Get-UserFiles {
    $directories = @(
        'Algorithms', 'App', 'BSP', 'Common', 'Devices', 'Middleware', 'Services'
    ) | ForEach-Object { Join-Path $ProjectRoot $_ }
    return @(Get-ChildItem -LiteralPath $directories -Recurse -File |
            Where-Object { $_.Extension -in '.c', '.h' })
}

Push-Location $ProjectRoot
try {
    $required = @(
        'Algorithms\low_pass_filter.c',
        'Algorithms\attitude_estimator.c',
        'Services\calibration_service.c',
        'Services\motion_service.c',
        'Services\sensor_service.c',
        'Middleware\csv_telemetry.c',
        'host\motionctl.py',
        'tools\test-python.ps1',
        'docs\phase-03-calibration-attitude.md'
    )
    $missing = @($required | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $ProjectRoot $_) -PathType Leaf)
        })
    Add-Check 'Required files' ($missing.Count -eq 0) `
        $(if ($missing) { $missing -join ', ' } else { 'all present' })

    $version = Get-Content -LiteralPath (Join-Path $ProjectRoot 'App\app_version.h') `
        -Raw -Encoding UTF8
    Add-Check 'Version at least 0.3.0' `
        ($version -match 'APP_VERSION_STRING\s+"(?:0\.[3-9]\.[0-9]+|[1-9][0-9]*\.[0-9]+\.[0-9]+)"') 'firmware version'

    $userFiles = Get-UserFiles
    $dynamic = @($userFiles |
            Select-String -Pattern '\b(?:malloc|calloc|realloc)\s*\(')
    Add-Check 'No dynamic memory' ($dynamic.Count -eq 0) 'user C modules'
    $delay = @($userFiles | Select-String -Pattern '\bHAL_Delay\s*\(')
    Add-Check 'No HAL_Delay' ($delay.Count -eq 0) 'user C modules'

    $algorithmFiles = @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'Algorithms') `
            -Recurse -File)
    $algorithmHal = @($algorithmFiles |
            Select-String -Pattern '(?i)stm32|HAL_|main\.h|i2c\.h')
    Add-Check 'Algorithms portable' ($algorithmHal.Count -eq 0) 'no HAL dependency'

    $floatLogs = @($userFiles |
            Select-String -Pattern 'Logger_.*%[-+0-9.*]*f')
    Add-Check 'No float log formatting' ($floatLogs.Count -eq 0) 'integer logs only'

    $calibration = Get-Content -LiteralPath `
        (Join-Path $ProjectRoot 'Services\calibration_service.c') -Raw -Encoding UTF8
    Add-Check 'Calibration non-blocking' `
        ($calibration -notmatch '\b(?:while|for)\s*\(') 'one sample per call'

    $attitude = Get-Content -LiteralPath `
        (Join-Path $ProjectRoot 'Algorithms\attitude_estimator.c') -Raw -Encoding UTF8
    Add-Check 'Attitude real dt' `
        (($attitude -match 'timestamp_ms\s*-\s*estimator->last_timestamp_ms') -and
         ($attitude -match 'dt_seconds')) 'timestamp-derived dt'
    Add-Check 'Timestamp wrap safe' `
        ($attitude -match 'uint32_t\s+elapsed_ms') 'unsigned elapsed time'

    $csv = Get-Content -LiteralPath `
        (Join-Path $ProjectRoot 'Middleware\csv_telemetry.c') -Raw -Encoding UTF8
    $schema = 'timestamp_ms,sequence,status_flags,calibrated'
    Add-Check 'Stable CSV schema' ($csv -match [regex]::Escape($schema)) '12 integer columns'

    $python = Get-Content -LiteralPath (Join-Path $ProjectRoot 'host\motionctl.py') `
        -Raw -Encoding UTF8
    Add-Check 'Simulation label' ($python -match 'SIMULATED DATA') `
        'simulation is explicitly identified'

    $trackedBuild = @(& git -C $ProjectRoot ls-files |
            Where-Object { $_ -match '^(?:build|build-host|data)/' })
    Add-Check 'Build outputs untracked' ($trackedBuild.Count -eq 0) 'no generated outputs'

    $readme = Get-Content -LiteralPath (Join-Path $ProjectRoot 'README.md') `
        -Raw -Encoding UTF8
    Add-Check 'Hardware validation documented' `
        (($readme -match 'Phase 3: Calibration and Attitude Pipeline') -and
         ($readme -match 'artifacts/hardware-validation/') -and
         ($readme -match 'Roll/Pitch')) `
        'verified behavior and remaining accuracy boundary are explicit'

    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $null = & git -C $ProjectRoot diff --check 2>$null
    $diffPassed = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $savedPreference
    Add-Check 'Git diff format' $diffPassed 'no whitespace errors'
}
finally {
    Pop-Location
}

if ($script:Failures -ne 0) {
    Write-Host "Phase 3 checks failed: $script:Failures" -ForegroundColor Red
    exit 1
}
Write-Host 'Phase 3 checks passed.' -ForegroundColor Green
exit 0
