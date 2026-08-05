[CmdletBinding()]
param()
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;$pidFile=Join-Path $root 'artifacts\phase07\.node-red.pid'
if(-not(Test-Path $pidFile)){Write-Host 'No project Node-RED PID file';exit 0}
$nodeRedPid=[int](Get-Content $pidFile -Raw);$p=Get-CimInstance Win32_Process -Filter "ProcessId=$nodeRedPid" -ErrorAction SilentlyContinue;$userDir=Join-Path $root 'artifacts\phase07\node-red-user'
if($p -and $p.CommandLine.Contains($userDir)){Stop-Process -Id $nodeRedPid -Force;Write-Host "Stopped project Node-RED PID=$nodeRedPid"}elseif($p){Write-Error 'PID is not project Node-RED';exit 2}
Remove-Item $pidFile -Force
