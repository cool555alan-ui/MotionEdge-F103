[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Port,
    [string]$ServoModel = 'NOT_PROVIDED',
    [double]$Duration = 600
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$null = chcp 65001
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = Join-Path $root 'host'
Push-Location $root
try {
    python .\host\phase9_hardware_validate.py --port $Port --baud 115200 `
        --duration $Duration --servo-model $ServoModel --output .\artifacts\phase09
    exit $LASTEXITCODE
}
finally { Pop-Location }
