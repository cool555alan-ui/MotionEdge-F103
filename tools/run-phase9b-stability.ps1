[CmdletBinding()]
param(
    [string]$Port = 'COM4',
    [int]$Baud = 115200,
    [int]$SegmentSeconds = 120,
    [ValidateSet('all', 'final', 'continuous')][string]$Mode = 'all'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$hostRoot = Join-Path $projectRoot 'host'
$artifactRoot = Join-Path $projectRoot 'artifacts\phase09\pid-attitude\stability-600s'
$env:PYTHONIOENCODING = 'utf-8'

function Invoke-MotionCtl {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & python -m motionctl @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "motionctl failed ($LASTEXITCODE): $($Arguments -join ' ')"
    }
}

function Invoke-ControlCapture {
    param([string]$Name, [string]$OutputPath)

    New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
    $summaryPath = Join-Path $OutputPath 'control-experiment-summary.json'
    $csvPath = Join-Path $OutputPath 'control-experiment.csv'
    # Remove only this segment's generated outputs so a retry cannot reuse stale PASS evidence.
    Remove-Item -LiteralPath $summaryPath, $csvPath -Force -ErrorAction SilentlyContinue
    $python = (Get-Command python -ErrorAction Stop).Source
    $captureArguments = @(
        '-m', 'motionctl', 'control', 'characterize',
        '--port', $Port, '--baud', [string]$Baud,
        '--duration', [string]$SegmentSeconds, '--output', $OutputPath
    )
    $started = Get-Date
    $process = Start-Process -FilePath $python -ArgumentList $captureArguments `
        -PassThru -NoNewWindow

    while (-not $process.HasExited) {
        $elapsed = [Math]::Min($SegmentSeconds,
            [int]((Get-Date) - $started).TotalSeconds)
        $remaining = [Math]::Max(0, $SegmentSeconds - $elapsed)
        $percent = [Math]::Min(100,
            [int](100.0 * $elapsed / $SegmentSeconds))
        $phase = if ($Name -eq 'continuous-final') {
            if ($elapsed -lt 120) { 'STILL' }
            elseif ($elapsed -lt 240) { 'ROLL MOTION' }
            elseif ($elapsed -lt 360) { 'STILL' }
            elseif ($elapsed -lt 480) { 'PITCH MOTION' }
            else { 'STILL' }
        } else { $Name }
        Write-Host ("`r{0}: elapsed {1,3}s / {2}s, remaining {3,3}s ({4,3}%)" -f `
            $phase, $elapsed, $SegmentSeconds, $remaining, $percent) -NoNewline
        Start-Sleep -Seconds 1
        $process.Refresh()
    }
    $process.WaitForExit()
    Write-Host
    if (-not (Test-Path -LiteralPath $summaryPath) -or
        -not (Test-Path -LiteralPath $csvPath)) {
        throw "$Name capture did not create complete evidence"
    }
    $captureSummary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
    if ($captureSummary.status -ne 'PASS') {
        throw "$Name capture status is $($captureSummary.status)"
    }
}

function Invoke-StabilitySegment {
    param(
        [string]$Name,
        [ValidateSet('roll', 'pitch')][string]$Axis,
        [string]$Prompt
    )

    Read-Host $Prompt | Out-Null
    Invoke-MotionCtl control axis $Axis --port $Port --baud $Baud
    Invoke-MotionCtl control enable --axis $Axis --port $Port --baud $Baud
    Write-Host "$Name capture running for $SegmentSeconds seconds..."
    Invoke-ControlCapture $Name (Join-Path $artifactRoot $Name)
    Invoke-MotionCtl control disable --port $Port --baud $Baud
    Invoke-MotionCtl control estop --port $Port --baud $Baud
}

Push-Location $hostRoot
try {
    if ($Mode -eq 'continuous') {
        Invoke-StabilitySegment 'continuous-final' 'pitch' `
            'Continuous 600s: secure SDA, keep still, then press Enter'
    }
    elseif ($Mode -eq 'all') {
        # Re-arm each segment so changing the axis also captures a safe new zero.
        Invoke-StabilitySegment '00-120-static' 'pitch' `
            'Stage 1/5: keep the board still, then press Enter'
        Invoke-StabilitySegment '120-240-roll' 'roll' `
            'Stage 2/5: prepare slow Roll motion, then press Enter'
        Invoke-StabilitySegment '240-360-static' 'roll' `
            'Stage 3/5: stop moving and keep still, then press Enter'
        Invoke-StabilitySegment '360-480-pitch' 'pitch' `
            'Stage 4/5: prepare slow Pitch motion, then press Enter'
    }
    if ($Mode -ne 'continuous') {
        Invoke-StabilitySegment '480-600-static' 'pitch' `
            'Stage 5/5: stop moving and keep still, then press Enter'
    }
}
finally {
    # Always disable and ESTOP after success, interruption, or command failure.
    & python -m motionctl control disable --port $Port --baud $Baud
    & python -m motionctl control estop --port $Port --baud $Baud
    & python -m motionctl control axis pitch --port $Port --baud $Baud
    & python -m motionctl control direction normal --port $Port --baud $Baud
    & python -m motionctl control deadband --degrees 1.0 --port $Port --baud $Baud
    Pop-Location
}

Write-Host '600-second validation complete: default Pitch/Normal/1.0 restored; ESTOP done.'
