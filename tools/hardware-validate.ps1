[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Port,
    [ValidateRange(1200, 3000000)]
    [int]$Baud = 115200,
    [Parameter(Mandatory = $true)]
    [string]$StlinkSerial,
    [string]$StlinkInfo = 'not recorded',
    [switch]$SkipProgrammerReset
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
    Sort-Object { [version](($_.Directory.Parent.Name -replace '\+.*$', '')) } -Descending |
    Select-Object -First 1

$PythonDependencies = Join-Path $ProjectRoot 'build-host\python-deps'
$PythonCandidates = @()
$PathPython = Get-Command python.exe -ErrorAction SilentlyContinue
if ($PathPython) {
    $PythonCandidates += $PathPython.Source
}
$PythonCandidates += Get-ChildItem `
        -Path (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\python.exe') `
        -File -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty FullName
$PythonCandidates = @($PythonCandidates | Where-Object { $_ } | Select-Object -Unique)
$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $PythonDependencies
$PythonExecutable = $null
foreach ($Candidate in $PythonCandidates) {
    & $Candidate -c 'import serial' 2>$null
    if ($LASTEXITCODE -eq 0) {
        $PythonExecutable = $Candidate
        break
    }
}
if (-not $PythonExecutable) {
    $env:PYTHONPATH = $PreviousPythonPath
    Write-Error 'No Python interpreter with pyserial was found; install host\requirements.txt first.'
    exit 2
}

# 真实验收必须明确指定唯一串口，脚本不在多端口环境下猜测。
Push-Location $ProjectRoot
try {
    $ValidationArguments = @(
        'host\hardware_validate.py',
        '--port', $Port,
        '--baud', $Baud,
        '--commit', $Commit,
        '--firmware-version', $Version,
        '--build-config', 'Debug',
        '--source-state', $SourceState,
        '--stlink', $StlinkInfo
    )
    if (-not $SkipProgrammerReset) {
        $ValidationArguments += @(
            '--programmer-cli', $ProgrammerCli.FullName,
            '--stlink-serial', $StlinkSerial
        )
    }
    & $PythonExecutable @ValidationArguments
    exit $LASTEXITCODE
}
finally {
    $env:PYTHONPATH = $PreviousPythonPath
    Pop-Location
}
