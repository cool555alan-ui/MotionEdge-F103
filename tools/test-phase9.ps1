[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $root 'host'
python -m unittest discover -s (Join-Path $root 'host\tests') -p 'test_phase9.py' -v
exit $LASTEXITCODE
