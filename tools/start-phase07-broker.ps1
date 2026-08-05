[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$artifacts=Join-Path $root 'artifacts\phase07'
$pidFile=Join-Path $artifacts '.broker.pid'
$log=Join-Path $artifacts 'broker.log'
$config=Join-Path $PSScriptRoot 'mosquitto-phase07.conf'
$listener=Get-NetTCPConnection -State Listen -LocalPort 1884 -ErrorAction SilentlyContinue
if($listener){Write-Error "127.0.0.1:1884 already used by PID $($listener.OwningProcess)";exit 2}
$exe=(Get-Command mosquitto.exe -ErrorAction SilentlyContinue).Source
if(-not $exe){$exe=Get-ChildItem -LiteralPath $env:ProgramFiles -Recurse -Filter mosquitto.exe -File -ErrorAction SilentlyContinue|Sort-Object FullName|Select-Object -First 1 -ExpandProperty FullName}
if(-not $exe){Write-Error 'mosquitto.exe not found';exit 3}
New-Item -ItemType Directory -Force $artifacts|Out-Null
$process=Start-Process -FilePath $exe -ArgumentList @('-c',$config,'-v') -WorkingDirectory $root -RedirectStandardOutput $log -RedirectStandardError (Join-Path $artifacts 'broker-error.log') -WindowStyle Hidden -PassThru
$process.Id|Set-Content -LiteralPath $pidFile -Encoding ascii
$deadline=(Get-Date).AddSeconds(5)
do{Start-Sleep -Milliseconds 100;$ready=Get-NetTCPConnection -State Listen -LocalPort 1884 -ErrorAction SilentlyContinue}while(-not $ready -and (Get-Date)-lt $deadline)
if(-not $ready){Write-Error 'Broker did not listen on 1884 within 5 seconds';exit 4}
Write-Host "Phase 7 Broker PID=$($process.Id) LISTEN=127.0.0.1:1884"
