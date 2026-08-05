[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Port,
    [ValidateRange(1200, 3000000)]
    [int]$Baud = 115200,
    [Parameter(Mandatory = $true)]
    [string]$StlinkSerial,
    [string]$StlinkInfo = 'not recorded',
    [ValidateRange(600, 86400)]
    [int]$DurationSeconds = 600
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Commit = (& git -C $ProjectRoot rev-parse HEAD).Trim()
$VersionHeader = Get-Content -Raw -Encoding UTF8 (Join-Path $ProjectRoot 'App\app_version.h')
$Version = [regex]::Match($VersionHeader, 'APP_VERSION_STRING\s+"([^"]+)"').Groups[1].Value
$SourceState = if (& git -C $ProjectRoot status --porcelain) {
    'working tree with uncommitted changes'
}
else {
    'clean working tree'
}
$ProgrammerCli = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA `
        'stm32cube\bundles\programmer\*\bin\STM32_Programmer_CLI.exe') `
    -File -ErrorAction Stop |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if (-not $ProgrammerCli) {
    Write-Error '未找到STM32_Programmer_CLI.exe。'
    exit 2
}

$PythonExecutable = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $PythonExecutable) {
    $PythonExecutable = Get-ChildItem `
            -Path (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\python.exe') `
            -File -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}

$ElfPath = Join-Path $ProjectRoot 'build\Debug\MotionEdge-F103.elf'
$SizeExecutable = Get-ChildItem `
        -Path (Join-Path $env:LOCALAPPDATA `
            'stm32cube\bundles\gnu-tools-for-stm32\*\bin\arm-none-eabi-size.exe') `
        -File -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName
if (-not (Test-Path -LiteralPath $ElfPath -PathType Leaf) -or
    -not $SizeExecutable) {
    Write-Error '未找到Debug ELF或arm-none-eabi-size。'
    exit 4
}
Write-Host ("SIZEEXEC=[{0}] ELFPATH=[{1}]" -f $SizeExecutable, $ElfPath)
$SizeOutput = & "$SizeExecutable" "$ElfPath"
$SizeFields = @($SizeOutput[-1] -split '\s+' | Where-Object { $_ })
if ($SizeFields.Count -lt 3) {
    Write-Error '无法解析Debug资源占用。'
    exit 5
}
$DebugFlash = [int]$SizeFields[0] + [int]$SizeFields[1]
$DebugRam = [int]$SizeFields[1] + [int]$SizeFields[2]
if (-not $PythonExecutable) {
    Write-Error '未找到Python。'
    exit 3
}

Push-Location $ProjectRoot
try {
    & $PythonExecutable 'host\rtos_hardware_validate.py' `
        '--port' $Port '--baud' $Baud `
        '--duration-seconds' $DurationSeconds `
        '--programmer-cli' $ProgrammerCli.FullName `
        '--stlink-serial' $StlinkSerial `
        '--stlink' $StlinkInfo `
        '--commit' $Commit `
        '--firmware-version' $Version `
        '--source-state' $SourceState `
        '--debug-flash' $DebugFlash `
        '--debug-ram' $DebugRam
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
