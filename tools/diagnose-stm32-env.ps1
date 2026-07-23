[CmdletBinding()]
param()

$ErrorActionPreference = 'SilentlyContinue'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:Rows = @()

function Add-Result {
    param(
        [string]$Name,
        [ValidateSet('OK','WARN','FAIL')][string]$Level,
        [string]$Detail
    )
    $script:Rows += [pscustomobject]@{ Name = $Name; Level = $Level; Detail = $Detail }
    $color = switch ($Level) { 'OK' { 'Green' } 'WARN' { 'Yellow' } default { 'Red' } }
    Write-Host ("[{0}] {1}: {2}" -f $Level, $Name, $Detail) -ForegroundColor $color
}

function Find-CommandOrFile {
    param([string]$CommandName, [string[]]$Candidates)
    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $matches = Get-ChildItem -Path $candidate -File -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending
        if ($matches) { return $matches[0].FullName }
    }
    return $null
}

function Find-Cube {
    $command = Get-Command cube -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $pattern = Join-Path $env:USERPROFILE '.vscode\extensions\stmicroelectronics.stm32cube-ide-core-*-win32-x64\resources\binaries\win32\x86_64\cube.exe'
    return Find-CommandOrFile -CommandName '__cube_not_on_path__' -Candidates @($pattern)
}

function Resolve-CubeTool {
    param([string]$CubePath, [string]$ToolName)
    if (-not $CubePath) { return $null }
    $text = & $CubePath --resolve $ToolName 2>&1 | Out-String
    if ($text -match "Command:\s+'([^']+)'") {
        $path = $matches[1] -replace '/', '\'
        if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
    }
    return $null
}

function Find-CubeMX {
    $command = Get-Command STM32CubeMX -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $patterns = @(
        'C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeMX\STM32CubeMX.exe',
        'C:\Program Files\STMicroelectronics\STM32CubeMX\STM32CubeMX.exe',
        'C:\Program Files (x86)\STMicroelectronics\STM32Cube\STM32CubeMX\STM32CubeMX.exe',
        'C:\ST\STM32CubeMX*\STM32CubeMX.exe',
        (Join-Path $env:LOCALAPPDATA 'STMicroelectronics\STM32CubeMX*\STM32CubeMX.exe')
    )
    return Find-CommandOrFile -CommandName '__cubemx_not_on_path__' -Candidates $patterns
}

Write-Host 'STM32 environment diagnosis' -ForegroundColor Cyan
Write-Host ("Project: {0}" -f $ProjectRoot) -ForegroundColor Cyan

$code = Find-CommandOrFile -CommandName 'code' -Candidates @(
    'C:\Program Files\Microsoft VS Code\bin\code.cmd',
    (Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\bin\code.cmd'),
    'E:\Microsoft VS Code\bin\code.cmd'
)
Add-Result 'VS Code CLI' $(if ($code) { 'OK' } else { 'FAIL' }) $(if ($code) { $code } else { '未找到 code 命令或常见安装路径' })

$stExtension = $false
if ($code) {
    $extensions = & $code --list-extensions 2>$null
    $stExtension = [bool]($extensions | Where-Object { $_ -ieq 'stmicroelectronics.stm32-vscode-extension' })
}
if (-not $stExtension) {
    $stExtension = [bool](Get-ChildItem (Join-Path $env:USERPROFILE '.vscode\extensions\stmicroelectronics.stm32-vscode-extension-*') -Directory -ErrorAction SilentlyContinue)
}
Add-Result 'ST 官方 VS Code 扩展' $(if ($stExtension) { 'OK' } else { 'FAIL' }) $(if ($stExtension) { 'stmicroelectronics.stm32-vscode-extension 已安装' } else { '未检测到官方扩展' })

$cube = Find-Cube
Add-Result 'Cube CLI' $(if ($cube) { 'OK' } else { 'WARN' }) $(if ($cube) { $cube } else { '未找到；可能需要重载 VS Code 激活扩展' })

$cubeMX = Find-CubeMX
Add-Result 'STM32CubeMX' $(if ($cubeMX) { 'OK' } else { 'FAIL' }) $(if ($cubeMX) { $cubeMX } else { '未在 PATH、卸载信息对应目录或常见安装目录中找到' })

$git = Find-CommandOrFile -CommandName 'git' -Candidates @('C:\Program Files\Git\cmd\git.exe', 'E:\Git\cmd\git.exe')
Add-Result 'Git' $(if ($git) { 'OK' } else { 'FAIL' }) $(if ($git) { (& $git --version) } else { '未找到' })

$gcc = Find-CommandOrFile -CommandName 'arm-none-eabi-gcc' -Candidates @(
    'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\*\bin\arm-none-eabi-gcc.exe',
    'C:\Program Files\Arm GNU Toolchain arm-none-eabi\*\bin\arm-none-eabi-gcc.exe',
    (Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\gnu-tools-for-stm32\*\bin\arm-none-eabi-gcc.exe')
)
Add-Result 'Arm GCC' $(if ($gcc) { 'OK' } else { 'FAIL' }) $(if ($gcc) { $gcc } else { '未找到' })

$cmake = Find-CommandOrFile -CommandName 'cmake' -Candidates @((Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\cmake\*\bin\cmake.exe'))
if (-not $cmake) { $cmake = Resolve-CubeTool -CubePath $cube -ToolName 'cmake' }
Add-Result 'CMake' $(if ($cmake) { 'OK' } else { 'FAIL' }) $(if ($cmake) { $cmake } else { '未找到' })

$ninja = Find-CommandOrFile -CommandName 'ninja' -Candidates @((Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\ninja\*\bin\ninja.exe'))
if (-not $ninja) { $ninja = Resolve-CubeTool -CubePath $cube -ToolName 'ninja' }
Add-Result 'Ninja' $(if ($ninja) { 'OK' } else { 'FAIL' }) $(if ($ninja) { $ninja } else { '未找到' })

$programmer = Find-CommandOrFile -CommandName 'STM32_Programmer_CLI' -Candidates @(
    'C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe',
    (Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\programmer\*\bin\STM32_Programmer_CLI.exe')
)
if (-not $programmer) { $programmer = Resolve-CubeTool -CubePath $cube -ToolName 'programmer' }
Add-Result 'STM32CubeProgrammer CLI' $(if ($programmer) { 'OK' } else { 'FAIL' }) $(if ($programmer) { $programmer } else { '未找到' })

$gdbServer = Find-CommandOrFile -CommandName 'ST-LINK_gdbserver' -Candidates @(
    (Join-Path $env:LOCALAPPDATA 'stm32cube\bundles\stlink-gdbserver\*\bin\ST-LINK_gdbserver.exe'),
    'C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\ST-LINK_gdbserver.exe'
)
if (-not $gdbServer) { $gdbServer = Resolve-CubeTool -CubePath $cube -ToolName 'stlink-gdbserver' }
$driver = Get-ItemProperty @(
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
) -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'STLinkWinUSB|ST-LINK|STMicroelectronics.*WinUSB' } | Select-Object -First 1
$stLinkReady = [bool]($gdbServer -and $driver)
Add-Result 'ST-LINK 调试支持' $(if ($stLinkReady) { 'OK' } elseif ($gdbServer -or $driver) { 'WARN' } else { 'FAIL' }) ("GDB Server={0}; 驱动={1}" -f $(if ($gdbServer) { $gdbServer } else { '未找到' }), $(if ($driver) { $driver.DisplayName } else { '未找到' }))

$f1Pack = Get-ChildItem (Join-Path $env:LOCALAPPDATA 'stm32cube\packs\STMicroelectronics\stm32f1xx_dfp\*') -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
Add-Result 'STM32F1 设备包' $(if ($f1Pack) { 'OK' } else { 'WARN' }) $(if ($f1Pack) { $f1Pack.FullName } else { '未检测到已展开的 STM32F1 DFP' })

$ioc = @(Get-ChildItem -LiteralPath $ProjectRoot -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.ioc', '.ioc2' })
$cmakeLists = Test-Path -LiteralPath (Join-Path $ProjectRoot 'CMakeLists.txt') -PathType Leaf
$presets = Test-Path -LiteralPath (Join-Path $ProjectRoot 'CMakePresets.json') -PathType Leaf
Add-Result 'CubeMX 配置文件' $(if ($ioc.Count -gt 0) { 'OK' } else { 'WARN' }) $(if ($ioc.Count -gt 0) { ($ioc.Name -join ', ') } else { '尚未生成 .ioc/.ioc2' })
Add-Result 'CMake 工程文件' $(if ($cmakeLists -and $presets) { 'OK' } else { 'WARN' }) ("CMakeLists.txt={0}; CMakePresets.json={1}" -f $cmakeLists, $presets)

$canCreate = [bool]$cubeMX
$canBuild = [bool]($gcc -and $cmake -and $ninja -and $cmakeLists -and $presets)
$canFlash = [bool]($programmer -and $canBuild)
$canDebug = [bool]($gdbServer -and $driver -and $canBuild)

Write-Host ''
Write-Host 'Readiness summary' -ForegroundColor Cyan
Add-Result '创建 CubeMX 项目' $(if ($canCreate) { 'OK' } else { 'FAIL' }) $(if ($canCreate) { '具备条件' } else { '需要安装并验证 STM32CubeMX' })
Add-Result '编译 STM32 项目' $(if ($canBuild) { 'OK' } else { 'WARN' }) $(if ($canBuild) { '具备条件' } else { '工具已就绪时仍需 CubeMX 生成 CMake 工程' })
Add-Result '烧录 STM32 项目' $(if ($canFlash) { 'OK' } else { 'WARN' }) $(if ($canFlash) { '具备工具与工程条件' } else { 'CubeProgrammer 已就绪时仍需成功构建固件' })
Add-Result '调试 STM32 项目' $(if ($canDebug) { 'OK' } else { 'WARN' }) $(if ($canDebug) { '具备工具、驱动与工程条件' } else { 'ST-LINK 工具/驱动已就绪时仍需成功构建固件' })
