[CmdletBinding()]
param()
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH=Join-Path $root 'host'
python -m unittest discover -s (Join-Path $root 'host\tests') -p 'test_phase8.py' -v
exit $LASTEXITCODE
