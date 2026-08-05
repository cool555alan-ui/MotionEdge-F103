[CmdletBinding()]
param()
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot
Push-Location $root
try{python -m unittest discover -s host\tests -p 'test_phase7.py' -v;exit $LASTEXITCODE}finally{Pop-Location}
