[CmdletBinding()]
param()
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot
$required=@('host\motionctl\attitude_metrics.py','host\motionctl\characterization.py','host\motionctl\experiment.py','host\motionctl\tuning.py','host\motionctl\tuning_profiles.py','host\motionctl\phase08_report.py','docs\coordinate-convention.md','tools\test-phase8.ps1')
foreach($file in $required){if(-not(Test-Path (Join-Path $root $file))){Write-Error "Missing Phase 8 file: $file";exit 2}}
$help=python -m motionctl --help 2>&1|Out-String
if($help-notmatch'characterize'-or$help-notmatch'\btune\b'){Write-Error 'Phase 8 CLI missing';exit 3}
$metrics=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'host\motionctl\attitude_metrics.py')
if($metrics-match'import serial|SerialTransport|DeviceClient'){Write-Error 'Statistics layer depends on serial';exit 4}
$profiles=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'host\motionctl\tuning_profiles.py')
if($profiles-notmatch'SCORE_WEIGHTS'-or$profiles-notmatch'THRESHOLDS'){Write-Error 'Central tuning profiles missing';exit 5}
$source=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'host\motionctl\characterization.py')
if($source-match'PASS\s*=|hardcoded.*PASS'){Write-Error 'Hard-coded result found';exit 6}
if($source-notmatch'preserve_configuration'){Write-Error 'Configuration restoration missing';exit 7}
$all=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'host\motionctl\phase08_report.py')
if($all-notmatch'absolute Yaw'-or$all-notmatch'uncertainty'){Write-Error 'Yaw/reference limitations missing';exit 8}
$firmware=git -C $root diff --name-only HEAD -- Inc Src Services Devices Algorithms Core
if($firmware){Write-Error 'Unexpected firmware changes or new RTOS work';exit 9}
$tracked=@(git -C $root ls-files 'artifacts/phase08/**/samples.csv' 'artifacts/phase08/**/*-raw.csv')
if($tracked.Count){Write-Error 'Large raw Phase 8 data tracked';exit 10}
Write-Host '[PASS] Phase 8 CLI, pure statistics, centralized weights, restoration, limitations and artifacts'
