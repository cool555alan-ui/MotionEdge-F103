[CmdletBinding()]
param([string]$BaseUrl='http://127.0.0.1:1880/red')
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;$target=Join-Path $root 'node-red\flows\motionedge-phase07-export.json'
$current=Invoke-RestMethod -Method Get -Uri "$BaseUrl/flows" -Headers @{'Node-RED-API-Version'='v2'} -TimeoutSec 5
$ids=@('p7tab00000000001','p7broker0000001');$phase=@($current.flows|Where-Object{$_.z-eq'p7tab00000000001'-or$_.id-in$ids-or$_.server-eq'p7wslistener001'-or$_.id-eq'p7wslistener001'})
$phase|ConvertTo-Json -Depth 100|Set-Content -Encoding UTF8 $target;Write-Host "Exported $($phase.Count) Phase 7 nodes to $target"
