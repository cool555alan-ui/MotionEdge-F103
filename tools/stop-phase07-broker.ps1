[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$pidFile=Join-Path $root 'artifacts\phase07\.broker.pid'
if(-not(Test-Path -LiteralPath $pidFile)){Write-Host 'No project Broker PID file';exit 0}
$brokerPid=[int](Get-Content -LiteralPath $pidFile -Raw)
$process=Get-CimInstance Win32_Process -Filter "ProcessId=$brokerPid" -ErrorAction SilentlyContinue
if($process -and $process.Name -eq 'mosquitto.exe' -and $process.CommandLine -like '*mosquitto-phase07.conf*'){
  Stop-Process -Id $brokerPid -Force
  Write-Host "Stopped project Broker PID=$brokerPid"
}elseif($process){Write-Error 'PID is not the project Broker';exit 2}
Remove-Item -LiteralPath $pidFile -Force
