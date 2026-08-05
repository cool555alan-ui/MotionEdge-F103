[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$exeDir=Split-Path -Parent (Get-ChildItem -LiteralPath $env:ProgramFiles -Recurse -Filter mosquitto.exe -File -ErrorAction SilentlyContinue|Sort-Object FullName|Select-Object -First 1 -ExpandProperty FullName)
if(-not $exeDir){Write-Error 'Mosquitto tools not found';exit 2}
$topic="motionedge/v1/diagnostics/$([guid]::NewGuid())"
$out=Join-Path $env:TEMP "motionedge-phase07-$([guid]::NewGuid()).txt"
$sub=Start-Process -FilePath (Join-Path $exeDir 'mosquitto_sub.exe') -ArgumentList @('-h','127.0.0.1','-p','1884','-t',$topic,'-C','1','-W','5') -RedirectStandardOutput $out -WindowStyle Hidden -PassThru
Start-Sleep -Milliseconds 300
& (Join-Path $exeDir 'mosquitto_pub.exe') -h 127.0.0.1 -p 1884 -t $topic -q 1 -m 'phase07-loopback'
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
$sub.WaitForExit(6000)|Out-Null
$value=if(Test-Path $out){(Get-Content -LiteralPath $out -Raw).Trim()}else{''}
Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue
if($value -ne 'phase07-loopback'){Write-Error 'MQTT loopback failed';exit 3}
Write-Host '[PASS] Phase 7 isolated Broker loopback'
