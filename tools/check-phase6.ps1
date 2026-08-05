[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$script:Failures = 0
function Check([string]$Name, [bool]$Passed, [string]$Detail) {
    if ($Passed) { Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green }
    else { ++$script:Failures; Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red }
}

Push-Location $Root
try {
    $env:PYTHONPATH = Join-Path $Root 'host'
    $help = python -m motionctl --help 2>&1
    $helpText = $help -join "`n"
    Check 'Module entry point' ($LASTEXITCODE -eq 0) 'python -m motionctl --help'
    $commands = @('ports','doctor','info','status','config','calibrate','stream','monitor','capture','validate','report','session')
    Check 'Core commands' (@($commands | Where-Object { $helpText -notmatch "\b$_\b" }).Count -eq 0) ($commands -join ', ')
    $protocol = Get-Content -Raw -Encoding UTF8 host\motionctl\protocol.py
    $transport = Get-Content -Raw -Encoding UTF8 host\motionctl\transport.py
    $metrics = Get-Content -Raw -Encoding UTF8 host\motionctl\metrics.py
    $validation = Get-Content -Raw -Encoding UTF8 host\motionctl\validation.py
    $device = Get-Content -Raw -Encoding UTF8 host\motionctl\device.py
    $capture = Get-Content -Raw -Encoding UTF8 host\motionctl\capture.py
    Check 'Single protocol implementation' `
        ((Get-ChildItem host\motionctl -File | Select-String -Pattern '^def crc16_ccitt_false' | Measure-Object).Count -eq 1) `
        'one CRC implementation in protocol.py'
    Check 'Protocol has no pyserial' ($protocol -notmatch '\bserial\b') 'pure protocol module'
    Check 'Metrics and validation have no serial dependency' `
        (($metrics -notmatch '(?:pyserial|import serial)') -and ($validation -notmatch '(?:pyserial|import serial)')) `
        'offline pure logic'
    Check 'Transport lifecycle' `
        (($transport -match 'def open') -and ($transport -match 'def close') -and
         ($transport -match 'def flush_input') -and ($transport -match 'def __enter__')) `
        'open/close/read/write/is_open/flush/context manager'
    Check 'Monotonic timeout' `
        (($device -match 'time\.monotonic') -and ($device -notmatch 'time\.time\(')) `
        'requests use monotonic clock'
    Check 'Atomic capture files' `
        (($capture -match '\.tmp') -and ($capture -match '\.replace\(') -and
         ($capture -match 'with .*open')) 'temporary files, replace and context managers'
    $pythonFiles = Get-ChildItem host\motionctl -File -Filter '*.py'
    $hardcodedCom = @($pythonFiles | Select-String -Pattern '["'']COM\d+["'']')
    Check 'No hard-coded COM port' ($hardcodedCom.Count -eq 0) 'ports always supplied or enumerated'
    $hardcodedIdentity = @($pythonFiles | Select-String -Pattern 'who_am_i\s*=\s*0x70')
    Check 'No fabricated device identity' ($hardcodedIdentity.Count -eq 0) 'missing fields remain NOT_AVAILABLE'
    Check 'Validation profile' (Test-Path host\motionctl\validation_profile.py) 'central thresholds'
    Check 'Required documentation' `
        ((Test-Path docs\phase-06-python-device-tools.md) -and
         (Test-Path docs\motionctl-cli-reference.md) -and
         (Test-Path docs\automated-report-format.md)) 'three Phase 6 documents'
    $versionText = (python -m motionctl --version 2>&1 | Select-Object -First 1)
    try { $toolVersion = [version]$versionText } catch { $toolVersion = [version]'0.0.0' }
    Check 'Tool version' ($toolVersion -ge [version]'0.6.0') "$toolVersion (Phase 6 minimum 0.6.0)"
    $trackedTemp = @(git ls-files 'artifacts/phase06/**/serial-raw.*' 'artifacts/phase06/**/telemetry.csv')
    Check 'Temporary captures untracked' ($trackedTemp.Count -eq 0) 'raw and telemetry CSV ignored'
    & powershell -ExecutionPolicy Bypass -File tools\test-phase6.ps1
    Check 'Phase 6 Python tests' ($LASTEXITCODE -eq 0) 'test_phase6.py'
    git diff --check
    Check 'Git diff format' ($LASTEXITCODE -eq 0) 'no whitespace errors'
}
finally { Pop-Location }
if ($script:Failures) { Write-Error "Phase 6 checks failed: $script:Failures"; exit 1 }
Write-Host 'Phase 6 checks passed.' -ForegroundColor Green
