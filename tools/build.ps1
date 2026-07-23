[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PresetsPath = Join-Path $ProjectRoot 'CMakePresets.json'

if (-not (Test-Path -LiteralPath $PresetsPath -PathType Leaf)) {
    Write-Error '请先使用STM32CubeMX生成CMake + GCC工程'
    exit 2
}

try {
    $presets = Get-Content -LiteralPath $PresetsPath -Raw | ConvertFrom-Json
} catch {
    Write-Error ("无法读取 CMakePresets.json: {0}" -f $_.Exception.Message)
    exit 3
}

$buildNames = @($presets.buildPresets | ForEach-Object { $_.name })
$configureNames = @($presets.configurePresets | ForEach-Object { $_.name })
Write-Host ("可用 configure presets: {0}" -f $(if ($configureNames) { $configureNames -join ', ' } else { '无' }))
Write-Host ("可用 build presets: {0}" -f $(if ($buildNames) { $buildNames -join ', ' } else { '无' }))

$cmake = Get-Command cmake -ErrorAction SilentlyContinue
if (-not $cmake) {
    $cmakePath = Get-ChildItem (Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\cmake\*\bin\cmake.exe') -File -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    if ($cmakePath) { $cmake = [pscustomobject]@{ Source = $cmakePath } }
}
if (-not $cmake) {
    Write-Error '未找到 CMake。请在 STM32 Bundle Manager 中安装推荐稳定 Bundle。'
    exit 4
}

$selectedBuild = $buildNames | Where-Object { $_ -ieq 'debug' } | Select-Object -First 1
if (-not $selectedBuild) { $selectedBuild = $buildNames | Select-Object -First 1 }

Push-Location $ProjectRoot
try {
    if ($selectedBuild) {
        Write-Host ("执行 build preset: {0}" -f $selectedBuild)
        & $cmake.Source --build --preset $selectedBuild
    } else {
        $selectedConfigure = $configureNames | Where-Object { $_ -ieq 'debug' } | Select-Object -First 1
        if (-not $selectedConfigure) { $selectedConfigure = $configureNames | Select-Object -First 1 }
        if (-not $selectedConfigure) {
            Write-Error 'CMakePresets.json 中没有可用 preset。'
            exit 5
        }
        Write-Host ("执行 configure preset: {0}" -f $selectedConfigure)
        & $cmake.Source --preset $selectedConfigure
        if ($LASTEXITCODE -eq 0) {
            Write-Host '未定义 build preset，使用 cmake --build --preset 不安全；请让 CubeMX 重新生成完整 presets。'
            exit 6
        }
    }
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
