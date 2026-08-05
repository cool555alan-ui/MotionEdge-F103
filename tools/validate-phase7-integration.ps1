[CmdletBinding()]
param()
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot
Push-Location $root
try{python host\phase7_integration_validate.py --config config\motionedge-gateway.toml;exit $LASTEXITCODE}finally{Pop-Location}
