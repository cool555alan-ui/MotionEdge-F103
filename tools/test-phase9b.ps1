[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    powershell -ExecutionPolicy Bypass -File .\tools\test-host.ps1
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $env:PYTHONPATH = Join-Path $root 'host'
    python -m unittest discover -s .\host\tests -p 'test_phase9b.py' -v
    exit $LASTEXITCODE
}
finally { Pop-Location }
