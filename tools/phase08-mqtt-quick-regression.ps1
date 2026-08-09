param(
    [Parameter(Mandatory = $true)]
    [string]$Port,
    [int]$Baud = 115200,
    [int]$MinimumFrames = 50
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "artifacts\phase08\final-report"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$before = Invoke-RestMethod "http://127.0.0.1:1880/motionedge/api/metrics" -TimeoutSec 5
$beforeCount = [int]$before.motion_received
$process = Start-Process python -ArgumentList @(
    "-m", "motionctl", "gateway", "run", "--config", "config\motionedge-gateway.toml"
) -WorkingDirectory $root -RedirectStandardOutput (Join-Path $out "mqtt-nodered-quick-regression.log") `
  -RedirectStandardError (Join-Path $out "mqtt-nodered-quick-regression-error.log") `
  -WindowStyle Hidden -PassThru

$metrics = $null
$delta = 0
$deadline = (Get-Date).AddSeconds(30)
try {
    do {
        Start-Sleep -Seconds 1
        if ($process.HasExited) { throw "gateway exited early with code $($process.ExitCode)" }
        $metrics = Invoke-RestMethod "http://127.0.0.1:1880/motionedge/api/metrics" -TimeoutSec 5
        $delta = [int]$metrics.motion_received - $beforeCount
    } while ($delta -lt $MinimumFrames -and (Get-Date) -lt $deadline)
}
finally {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    python -m motionctl stream stop --port $Port --baud $Baud | Out-Null
}

$checks = [ordered]@{
    motion_frames = $(if ($delta -ge $MinimumFrames) { "PASS" } else { "FAIL" })
    invalid_json = $(if ([int]$metrics.invalid_json -eq 0) { "PASS" } else { "FAIL" })
    schema_error = $(if ([int]$metrics.schema_error -eq 0) { "PASS" } else { "FAIL" })
    sequence_duplicate = $(if ([int]$metrics.duplicate_received -eq 0) { "PASS" } else { "FAIL" })
    sequence_regression = $(if ([int]$metrics.sequence_regression -eq 0) { "PASS" } else { "FAIL" })
    sequence_gap = $(if ([int]$metrics.sequence_gap -eq 0) { "PASS" } else { "FAIL" })
}
$result = [ordered]@{
    tested_at = (Get-Date).ToString("o")
    scope = "quick live-link regression; Phase 7 600 s evidence remains authoritative"
    motion_received_delta = $delta
    node_red_metrics = $metrics
    checks = $checks
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $out "mqtt-nodered-quick-regression.json") -Encoding UTF8
$result | ConvertTo-Json -Depth 8
if ($checks.Values -contains "FAIL") { exit 1 }
