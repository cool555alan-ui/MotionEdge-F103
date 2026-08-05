[CmdletBinding()]
param([double]$Seconds=600,[string]$Config='config\motionedge-gateway.toml',[switch]$TimedPrompts)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if($Seconds-lt 600){Write-Error 'Phase 7 real validation requires at least 600 seconds';exit 2}
Set-Location $root
$arguments=@('.\host\phase7_hardware_validate.py','--config',$Config,'--seconds',$Seconds)
if($TimedPrompts){$arguments+='--timed-prompts'}
python @arguments
exit $LASTEXITCODE
