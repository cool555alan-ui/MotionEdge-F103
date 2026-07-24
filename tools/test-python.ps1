[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OutputPath = Join-Path $ProjectRoot 'build-host\python-simulated.csv'

$python = Get-Command python, py -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) {
    Write-Error 'Python 3 was not found.'
    exit 2
}

$prefix = @()
if ($python.Name -eq 'py.exe' -or $python.Name -eq 'py') {
    $prefix = @('-3')
}

Push-Location $ProjectRoot
try {
    & $python.Source @prefix -m unittest discover -s host/tests -p 'test_*.py' -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python.Source @prefix host/motionctl.py simulate --seconds 0.2 --output $OutputPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python.Source @prefix host/motionctl.py validate $OutputPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python.Source @prefix host/motionctl.py summary $OutputPath
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
