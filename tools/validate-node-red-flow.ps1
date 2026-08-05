[CmdletBinding()]
param()
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;$path=Join-Path $root 'node-red\flows\motionedge-phase07.json'
$parsed=Get-Content -Raw -Encoding UTF8 $path|ConvertFrom-Json;$flows=@($parsed|ForEach-Object{$_});$ids=@($flows|ForEach-Object{$_.id})
if($ids.Count-ne @($ids|Sort-Object -Unique).Count){Write-Error 'Duplicate Node-RED node IDs';exit 2}
$types=@($flows.type);foreach($required in @('mqtt in','mqtt out','function','websocket out','http in','http response')){if($required-notin$types){Write-Error "Missing node type: $required";exit 3}}
$text=Get-Content -Raw -Encoding UTF8 $path
foreach($topic in @('motionedge/v1/devices/+/telemetry/motion','motionedge/v1/devices/+/telemetry/health','motionedge/v1/devices/+/state','motionedge/v1/devices/+/response')){if(-not$text.Contains($topic)){Write-Error "Missing Flow topic: $topic";exit 4}}
if($text-match '"command"\s*:\s*"(pwm|pid)"'){Write-Error 'Forbidden actuator command in Flow';exit 5}
Write-Host "[PASS] Node-RED Flow valid nodes=$($flows.Count) unique IDs and matching topics"
