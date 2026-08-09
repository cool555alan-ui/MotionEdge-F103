param(
    [Parameter(Mandatory = $true)]
    [string]$Port,
    [int]$Baud = 115200,
    [string]$Output = "artifacts/phase08/tuning/candidates"
)

$ErrorActionPreference = "Stop"
$profiles = @(
    @{ Name = "current";       Alpha = "0.20"; Gyro = "0.98" },
    @{ Name = "low_noise";     Alpha = "0.10"; Gyro = "0.985" },
    @{ Name = "fast_response"; Alpha = "0.40"; Gyro = "0.95" },
    @{ Name = "balanced";      Alpha = "0.15"; Gyro = "0.97" }
)

foreach ($profile in $profiles) {
    $summary = Join-Path (Join-Path $Output $profile.Name) "summary.json"
    if (Test-Path -LiteralPath $summary) {
        Write-Host ("Skipping completed candidate {0}" -f $profile.Name) -ForegroundColor DarkGray
        continue
    }
    Write-Host ""
    Write-Host ("Starting candidate {0}: alpha={1}, gyro_weight={2}" -f $profile.Name, $profile.Alpha, $profile.Gyro) -ForegroundColor Cyan
    python -m motionctl characterize candidate `
        --port $Port --baud $Baud --timeout 1 `
        --name $profile.Name --alpha $profile.Alpha --gyro-weight $profile.Gyro `
        --static-duration 120 --output (Join-Path $Output $profile.Name)
    if ($LASTEXITCODE -ne 0) {
        throw "Candidate $($profile.Name) failed with exit code $LASTEXITCODE"
    }
}

Write-Host "All candidate measurements completed; original configuration restored." -ForegroundColor Green
