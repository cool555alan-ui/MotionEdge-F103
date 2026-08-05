[CmdletBinding()]
param([string]$BaseUrl='http://127.0.0.1:1880/red')
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;$flowPath=Join-Path $root 'node-red\flows\motionedge-phase07.json';$artifacts=Join-Path $root 'artifacts\phase07';New-Item -ItemType Directory -Force $artifacts|Out-Null
try{$current=Invoke-RestMethod -Method Get -Uri "$BaseUrl/flows" -Headers @{'Node-RED-API-Version'='v2'} -TimeoutSec 5}catch{if($_.Exception.Response.StatusCode.value__-in 401,403){Write-Error 'Node-RED Admin API authentication required';exit 3};throw}
$backup=Join-Path $artifacts ("node-red-flows-backup-{0}.json"-f(Get-Date -Format 'yyyyMMdd-HHmmss'));$current|ConvertTo-Json -Depth 100|Set-Content -Encoding UTF8 $backup
$parsed=Get-Content -Raw -Encoding UTF8 $flowPath|ConvertFrom-Json;$incoming=@($parsed|ForEach-Object{$_});$existing=@($current.flows|ForEach-Object{$_});$incomingIds=@($incoming|ForEach-Object{$_.id})
$phaseTab=@($existing|Where-Object{$_.id-eq'p7tab00000000001'})
if($phaseTab.Count-gt 0-and$phaseTab[0].label-ne'MotionEdge Phase 7'){Write-Error 'Phase 7 tab ID belongs to another Flow; nothing deployed';exit 4}
$preserved=@($existing|Where-Object{$_.id-notin$incomingIds})
$body=@{rev=$current.rev;flows=@($preserved)+@($incoming)}|ConvertTo-Json -Depth 100
try{Invoke-RestMethod -Method Post -Uri "$BaseUrl/flows" -Headers @{'Node-RED-API-Version'='v2'} -ContentType 'application/json' -Body $body -TimeoutSec 20|Out-Null}catch{Write-Error "Deploy failed; backup=$backup; error=$($_.Exception.Message)";exit 5}
Start-Sleep -Seconds 2
try{$status=(Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://127.0.0.1:1880/motionedge/).StatusCode}catch{$status=0}
if($status-ne 200){Write-Error 'Flow deployed but page did not return HTTP 200';exit 6}
Write-Host "[PASS] Flow merged; backup=$backup page=http://127.0.0.1:1880/motionedge/"
