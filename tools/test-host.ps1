[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$HostBuildDirectory = Join-Path $ProjectRoot 'build-host'

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

$cmakeCommand = Get-Command cmake -ErrorAction SilentlyContinue
$cmakePath = if ($cmakeCommand) { $cmakeCommand.Source } else {
    Find-LatestFile @(
        (Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\cmake\*\bin\cmake.exe')
    )
}
if (-not $cmakePath) {
    Write-Error '未找到可用的 CMake。'
    exit 2
}

$ctestPath = Join-Path (Split-Path -Parent $cmakePath) 'ctest.exe'
if (-not (Test-Path -LiteralPath $ctestPath -PathType Leaf)) {
    Write-Error '未找到与 CMake 配套的 ctest。'
    exit 3
}

$compilerCommand = Get-Command gcc, clang, cl -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notlike 'arm-none-eabi-*' } |
    Select-Object -First 1
$compilerPath = if ($compilerCommand) { $compilerCommand.Source } else {
    Find-LatestFile @(
        'C:\msys64\ucrt64\bin\gcc.exe',
        'C:\Program Files\LLVM\bin\clang.exe'
    )
}
if (-not $compilerPath) {
    Write-Warning '未找到 Windows 本机 C 编译器；主机测试未运行。ARM 交叉编译器不能执行 Windows 测试。'
    exit 10
}
if ((Split-Path -Leaf $compilerPath) -like 'arm-none-eabi-*') {
    Write-Error '拒绝使用 ARM 交叉编译器构建 Windows 主机测试。'
    exit 11
}

$ninjaCommand = Get-Command ninja -ErrorAction SilentlyContinue
$ninjaPath = if ($ninjaCommand) { $ninjaCommand.Source } else {
    Find-LatestFile @(
        (Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\ninja\*\bin\ninja.exe')
    )
}
if (-not $ninjaPath) {
    Write-Error '未找到 Ninja，无法配置独立主机测试构建。'
    exit 4
}

Write-Host "主机编译器: $compilerPath"
Write-Host "主机构建目录: $HostBuildDirectory"

Push-Location $ProjectRoot
try {
    & $cmakePath -S 'Tests/Host' -B $HostBuildDirectory -G Ninja `
        "-DCMAKE_C_COMPILER:FILEPATH=$compilerPath" `
        "-DCMAKE_MAKE_PROGRAM:FILEPATH=$ninjaPath"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $cmakePath --build $HostBuildDirectory
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & $ctestPath --test-dir $HostBuildDirectory --output-on-failure
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
