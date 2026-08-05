[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PresetsPath = Join-Path $ProjectRoot 'CMakePresets.json'

function Find-LatestFile {
    param([string[]]$Patterns)

    foreach ($pattern in $Patterns) {
        $match = Get-ChildItem -Path $pattern -File -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($match) {
            return $match.FullName
        }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $PresetsPath -PathType Leaf)) {
    Write-Error '请先使用STM32CubeMX生成CMake + GCC工程'
    exit 2
}

try {
    $presets = Get-Content -LiteralPath $PresetsPath -Raw -Encoding UTF8 | ConvertFrom-Json
}
catch {
    Write-Error ("无法读取 CMakePresets.json: {0}" -f $_.Exception.Message)
    exit 3
}

$configureNames = @($presets.configurePresets |
        Where-Object { -not $_.hidden } |
        ForEach-Object { $_.name })
$buildNames = @($presets.buildPresets | ForEach-Object { $_.name })
$selectedConfigure = $configureNames |
    Where-Object { $_ -ieq 'Debug' } |
    Select-Object -First 1
if (-not $selectedConfigure) {
    $selectedConfigure = $configureNames | Select-Object -First 1
}
$selectedBuild = $buildNames |
    Where-Object { $_ -ieq 'Debug' } |
    Select-Object -First 1
if (-not $selectedBuild) {
    $selectedBuild = $buildNames | Select-Object -First 1
}
if (-not $selectedConfigure -or -not $selectedBuild) {
    Write-Error 'CMakePresets.json 中缺少可用的 configure 或 build preset。'
    exit 4
}

$cmakeCommand = Get-Command cmake -ErrorAction SilentlyContinue
$cmakePath = if ($cmakeCommand) { $cmakeCommand.Source } else {
    Find-LatestFile @(
        (Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\cmake\*\bin\cmake.exe')
    )
}
if (-not $cmakePath) {
    Write-Error '未找到 CMake。请在 STM32 Bundle Manager 中安装推荐稳定 Bundle。'
    exit 5
}

Write-Host ("可用 configure presets: {0}" -f ($configureNames -join ', '))
Write-Host ("可用 build presets: {0}" -f ($buildNames -join ', '))
Write-Host "执行 configure preset: $selectedConfigure"

Push-Location $ProjectRoot
try {
    & $cmakePath --preset $selectedConfigure
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    Write-Host "执行 build preset: $selectedBuild"
    & $cmakePath --build --preset $selectedBuild
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $selectedBuildDirectory = Join-Path $ProjectRoot ("build\{0}" -f $selectedBuild)
    if (-not (Test-Path -LiteralPath $selectedBuildDirectory -PathType Container)) {
        $selectedBuildDirectory = Join-Path $ProjectRoot 'build'
    }
    $elf = Get-ChildItem -LiteralPath $selectedBuildDirectory -Recurse -File `
            -Filter '*.elf' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $elf) {
        Write-Error '构建命令成功，但未找到 ELF 文件。'
        exit 6
    }

    $toolPatterns = @(
        (Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\gnu-tools-for-stm32\*\bin')
        'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\*\bin'
        'C:\Program Files\Arm GNU Toolchain arm-none-eabi\*\bin'
    )
    $sizePath = Find-LatestFile ($toolPatterns | ForEach-Object {
            Join-Path $_ 'arm-none-eabi-size.exe'
        })
    $objcopyPath = Find-LatestFile ($toolPatterns | ForEach-Object {
            Join-Path $_ 'arm-none-eabi-objcopy.exe'
        })

    $artifactBase = Join-Path $elf.DirectoryName $elf.BaseName
    $hexPath = "$artifactBase.hex"
    $binPath = "$artifactBase.bin"
    if ($objcopyPath) {
        & $objcopyPath -O ihex $elf.FullName $hexPath
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        & $objcopyPath -O binary $elf.FullName $binPath
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    else {
        Write-Warning '未找到 arm-none-eabi-objcopy；不会自动生成 HEX/BIN。'
    }

    $map = Get-ChildItem -LiteralPath $elf.DirectoryName -File -Filter '*.map' `
            -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    Write-Host "ELF: $($elf.FullName)"
    Write-Host ("MAP: {0}" -f $(if ($map) { $map.FullName } else { '未生成' }))
    Write-Host ("HEX: {0}" -f $(if (Test-Path -LiteralPath $hexPath) { $hexPath } else { '未生成' }))
    Write-Host ("BIN: {0}" -f $(if (Test-Path -LiteralPath $binPath) { $binPath } else { '未生成' }))

    if ($sizePath) {
        Write-Host '内存占用 (arm-none-eabi-size):'
        & $sizePath $elf.FullName
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    else {
        Write-Warning '未找到 arm-none-eabi-size，无法输出段大小。'
    }

    exit 0
}
finally {
    Pop-Location
}
