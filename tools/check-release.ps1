[CmdletBinding()]param()
$root=Split-Path -Parent $PSScriptRoot;Push-Location $root
try { python tools/check-release.py;exit $LASTEXITCODE } finally {Pop-Location}
