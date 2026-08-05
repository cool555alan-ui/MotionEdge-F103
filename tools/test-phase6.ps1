[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $Root 'host'
Push-Location $Root
try {
    python -m unittest discover -s host\tests -p 'test_phase6.py' -v
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
