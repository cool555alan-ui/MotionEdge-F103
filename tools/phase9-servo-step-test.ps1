[CmdletBinding()]
param(
    [string]$Port = 'COM4',
    [ValidateRange(1400,1600)][int]$PulseUs = 1450,
    [ValidateRange(100,900)][int]$HoldMs = 700
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $root 'host'
Push-Location $root
try {
    Write-Host 'One controlled step only: 1500 us -> target -> ESTOP.' -ForegroundColor Yellow
    Write-Host 'Verify external 5V, common GND, PA6 Signal, no load, and clear travel.'
    [void](Read-Host 'Press Enter when safe; close this window to abort')
    python -m motionctl actuator status --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read actuator status' }
    try {
        python -m motionctl actuator arm --port $Port
        if ($LASTEXITCODE -ne 0) { throw 'ARM failed' }
        Write-Host ("Short output: {0} us for {1} ms" -f $PulseUs, $HoldMs) -ForegroundColor Cyan
        python -m motionctl actuator set-pulse --port $Port --pulse-us $PulseUs
        if ($LASTEXITCODE -ne 0) { throw 'Pulse command failed' }
        Start-Sleep -Milliseconds $HoldMs
    }
    finally {
        python -m motionctl actuator stop --port $Port
        Write-Host 'ESTOP sent; PWM must now be Disabled.' -ForegroundColor Green
    }
    python -m motionctl actuator status --port $Port
    [void](Read-Host 'Record the observation, then press Enter to close')
}
finally { Pop-Location }
