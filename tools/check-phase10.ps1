[CmdletBinding()]param()
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;Push-Location $root
try {
  $version=(Get-Content VERSION -Raw).Trim()
  $required=@('Services/config_store.c','Services/config_store.h','Services/config_persistence.c','BSP/bsp_flash.c','BSP/config_flash_reserve.S','tools/check-firmware-size.py','.github/workflows/ci.yml','.github/workflows/release.yml','VERSION','CHANGELOG.md',"RELEASE_NOTES_v$version.md")
  foreach($file in $required){if(!(Test-Path $file)){throw "missing $file"}}
  $store=Get-Content Services/config_store.c -Raw
  foreach($token in 'CONFIG_COMMIT_MARKER','CONFIG_SCHEMA_VERSION','CONFIG_SLOT_A_ADDRESS','CONFIG_SLOT_B_ADDRESS','CONFIG_SAVE_RATE_LIMITED','ConfigStore_FactoryReset'){if($store -notmatch $token){throw "missing $token"}}
  python tools/check-firmware-size.py build/Debug/MotionEdge-F103.elf;if($LASTEXITCODE){exit $LASTEXITCODE}
  python tools/check-firmware-size.py build/Release/MotionEdge-F103.elf;if($LASTEXITCODE){exit $LASTEXITCODE}
  python -m json.tool node-red/flows/motionedge-phase07.json > $null
  git diff --check;if($LASTEXITCODE){exit $LASTEXITCODE}
  Write-Host '[PASS] Phase 10 static, dual-slot, safety, size, overlap, CI and release checks'
} finally {Pop-Location}
