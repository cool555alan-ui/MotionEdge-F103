[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$artifacts=Join-Path $root 'artifacts\phase07'
$userDir=Join-Path $artifacts 'node-red-user'
$pidFile=Join-Path $artifacts '.node-red.pid'
if(Get-NetTCPConnection -State Listen -LocalPort 1880 -ErrorAction SilentlyContinue){Write-Error 'Port 1880 already in use';exit 2}
$nodeRed=(Get-Command node-red.cmd -ErrorAction SilentlyContinue).Source
if(-not $nodeRed){$nodeRed=Join-Path $env:APPDATA 'npm\node-red.cmd'}
if(-not(Test-Path -LiteralPath $nodeRed)){Write-Error 'Node-RED not found';exit 3}
New-Item -ItemType Directory -Force $userDir|Out-Null
$settings=Join-Path $root 'node-red\settings.js'
$log=Join-Path $artifacts 'node-red.log'
$err=Join-Path $artifacts 'node-red-error.log'
$p=Start-Process -FilePath $nodeRed -ArgumentList @('--userDir',$userDir,'--settings',$settings) -WorkingDirectory $root -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Hidden -PassThru
$deadline=(Get-Date).AddSeconds(20)
do{Start-Sleep -Milliseconds 250;try{$ok=(Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 http://127.0.0.1:1880/red/).StatusCode}catch{$ok=0}}while($ok-ne 200 -and (Get-Date)-lt $deadline)
if($ok-ne 200){Write-Error 'Node-RED did not start within 20 seconds';exit 4}
$listener=Get-NetTCPConnection -State Listen -LocalPort 1880 -ErrorAction Stop|Select-Object -First 1
$nodePid=[int]$listener.OwningProcess
$nodeProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$nodePid"
if(-not$nodeProcess.CommandLine.Contains($userDir)){Write-Error 'Port 1880 listener is not the isolated project Node-RED';exit 5}
$nodePid|Set-Content -LiteralPath $pidFile -Encoding ascii
Write-Host "Node-RED PID=$nodePid URL=http://127.0.0.1:1880/red/"
