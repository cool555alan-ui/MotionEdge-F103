[CmdletBinding()]
param(
    [string]$Port,
    [ValidateRange(1200, 3000000)]
    [int]$Baud = 115200,
    [Parameter(Mandatory = $true)]
    [string]$StlinkSerial,
    [string]$StlinkInfo = 'not recorded',
    [ValidateRange(600, 86400)]
    [int]$DurationSeconds = 600,
    [int]$DebugFlash = 0,
    [int]$DebugRam = 0
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python.exe -ErrorAction Stop).Source
& $Python -c 'import serial' 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'The selected Python interpreter does not provide pyserial.'
}
if (-not $Port) {
        # Python enumerates real serial descriptions; multiple ports require selection.
        $PortJson = & $Python -c `
            'import json; from serial.tools import list_ports; print(json.dumps([{"device": p.device, "description": p.description, "hwid": p.hwid} for p in list_ports.comports()]))'
        $Ports = @($PortJson | ConvertFrom-Json)
        if ($Ports.Count -eq 0) {
            throw 'No Windows serial port was detected.'
        }
        Write-Host 'Python detected these serial ports:'
        for ($Index = 0; $Index -lt $Ports.Count; ++$Index) {
            Write-Host ("[{0}] {1} - {2} - {3}" -f ($Index + 1),
                    $Ports[$Index].device, $Ports[$Index].description, $Ports[$Index].hwid)
        }
        if ($Ports.Count -eq 1) {
            $Port = $Ports[0].device
        }
        else {
            $Selection = [int](Read-Host 'Multiple ports found; enter the port number')
            if (($Selection -lt 1) -or ($Selection -gt $Ports.Count)) {
                throw 'Invalid serial port number.'
            }
            $Port = $Ports[$Selection - 1].device
        }
}

$ProgrammerCli = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA `
        'stm32cube\bundles\programmer\*\bin\STM32_Programmer_CLI.exe') `
    -File -ErrorAction Stop |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName
$ElfPath = Join-Path $ProjectRoot 'build\Debug\MotionEdge-F103.elf'
if (($DebugFlash -eq 0) -or ($DebugRam -eq 0)) {
    $SizeExecutable = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA `
            'stm32cube\bundles\gnu-tools-for-stm32\*\bin\arm-none-eabi-size.exe') `
        -File -ErrorAction Stop |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
    $SizeOutput = & $SizeExecutable $ElfPath
    $SizeFields = @($SizeOutput[-1] -split '\s+' | Where-Object { $_ })
    $DebugFlash = [int]$SizeFields[0] + [int]$SizeFields[1]
    $DebugRam = [int]$SizeFields[1] + [int]$SizeFields[2]
}
$Commit = (& git -C $ProjectRoot rev-parse HEAD).Trim()
$VersionHeader = Get-Content -Raw -Encoding UTF8 (Join-Path $ProjectRoot 'App\app_version.h')
$Version = [regex]::Match($VersionHeader, 'APP_VERSION_STRING\s+"([^"]+)"').Groups[1].Value
$SourceState = if (& git -C $ProjectRoot status --porcelain) {
    'working tree with uncommitted changes'
} else {
    'clean working tree'
}

Push-Location $ProjectRoot
try {
    & $Python 'host\rtos_hardware_validate.py' `
        '--port' $Port '--baud' $Baud `
        '--duration-seconds' $DurationSeconds `
        '--programmer-cli' $ProgrammerCli `
        '--stlink-serial' $StlinkSerial `
        '--stlink' $StlinkInfo `
        '--commit' $Commit `
        '--firmware-version' $Version `
        '--source-state' $SourceState `
        '--debug-flash' $DebugFlash `
        '--debug-ram' $DebugRam
}
finally {
    Pop-Location
}
exit $LASTEXITCODE
