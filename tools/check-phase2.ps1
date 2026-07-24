[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:FailureCount = 0

function Add-Check {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Detail
    )

    if ($Passed) {
        Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green
    }
    else {
        ++$script:FailureCount
        Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red
    }
}

Push-Location $ProjectRoot
try {
    & (Join-Path $PSScriptRoot 'check-phase1.ps1')
    Add-Check 'Phase 1 regression' ($LASTEXITCODE -eq 0) 'foundation remains valid'

    $requiredFiles = @(
        'BSP\bsp_i2c.c',
        'BSP\bsp_i2c.h',
        'Devices\mpu6050.c',
        'Devices\mpu6050.h',
        'Services\i2c_scanner.c',
        'Services\i2c_scanner.h',
        'Tests\Host\test_i2c_scanner.c',
        'Tests\Host\test_mpu6050.c',
        'docs\phase-02-i2c-mpu6050.md'
    )
    $missingFiles = @($requiredFiles | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $ProjectRoot $_) -PathType Leaf)
        })
    Add-Check 'Phase 2 required files' ($missingFiles.Count -eq 0) `
        $(if ($missingFiles) { $missingFiles -join ', ' } else { 'all present' })

    $portableFiles = @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'Devices') `
            -Recurse -File -Include '*.c', '*.h')
    $portableFiles += @(Get-Item -LiteralPath @(
            (Join-Path $ProjectRoot 'Services\i2c_scanner.c'),
            (Join-Path $ProjectRoot 'Services\i2c_scanner.h')
        ))
    $halHits = @($portableFiles |
            Select-String -Pattern '(?i)stm32.*hal|#\s*include\s*"(?:main|i2c)\.h"')
    Add-Check 'Portable sensor modules' ($halHits.Count -eq 0) `
        $(if ($halHits) { 'HAL dependency found' } else { 'injected bus functions only' })

    $userDirectories = @('App', 'BSP', 'Common', 'Devices', 'Middleware', 'Services') |
        ForEach-Object { Join-Path $ProjectRoot $_ }
    $userFiles = @(Get-ChildItem -LiteralPath $userDirectories -Recurse -File |
            Where-Object { $_.Extension -in '.c', '.h' })
    $dynamicMemoryHits = @($userFiles |
            Select-String -Pattern '\b(?:malloc|calloc|realloc)\s*\(')
    Add-Check 'No dynamic memory' ($dynamicMemoryHits.Count -eq 0) `
        $(if ($dynamicMemoryHits) { 'dynamic allocation found' } else { 'none found' })

    $cmakeText = Get-Content -LiteralPath (Join-Path $ProjectRoot 'cmake\user_sources.cmake') `
        -Raw -Encoding UTF8
    $requiredSources = @('bsp_i2c.c', 'mpu6050.c', 'i2c_scanner.c')
    $missingSources = @($requiredSources |
            Where-Object { $cmakeText -notmatch [regex]::Escape($_) })
    Add-Check 'Phase 2 CMake sources' ($missingSources.Count -eq 0) `
        $(if ($missingSources) { $missingSources -join ', ' } else { 'all integrated' })

    $appText = Get-Content -LiteralPath (Join-Path $ProjectRoot 'App\app_main.c') `
        -Raw -Encoding UTF8
    $sensorServicePath = Join-Path $ProjectRoot 'Services\sensor_service.c'
    $sensorText = if (Test-Path -LiteralPath $sensorServicePath) {
        Get-Content -LiteralPath $sensorServicePath -Raw -Encoding UTF8
    }
    else {
        ''
    }
    Add-Check 'I2C scan integration' ($appText -match '\bI2cScanner_Step\s*\(') `
        'single-step scan in main loop'
    Add-Check 'WHO_AM_I integration' ($appText -match '\bMpu6050_ReadWhoAmI\s*\(') `
        'application reads sensor identity'
    Add-Check 'Raw sample integration' `
        (($appText + $sensorText) -match '\bMpu6050_ReadRaw\s*\(') `
        'application sensor pipeline reads raw samples periodically'

    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $diffCheckOutput = @(& git -C $ProjectRoot diff --check 2>$null)
    $diffCheckPassed = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $savedErrorActionPreference
    Add-Check 'Git diff format' $diffCheckPassed `
        $(if ($diffCheckOutput) { $diffCheckOutput -join '; ' } else { 'passed' })
}
finally {
    Pop-Location
}

if ($script:FailureCount -ne 0) {
    Write-Host "Phase 2 checks failed: $script:FailureCount" -ForegroundColor Red
    exit 1
}

Write-Host 'Phase 2 checks passed.' -ForegroundColor Green
exit 0
