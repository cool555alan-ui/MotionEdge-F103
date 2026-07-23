[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:FailureCount = 0

function Add-Check {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Detail
    )

    if ($Passed) {
        Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green
    }
    else {
        ++$script:FailureCount
        Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red
    }
}

function Get-TextFiles {
    param([string[]]$Directories)

    $files = @()
    foreach ($directory in $Directories) {
        $path = Join-Path $ProjectRoot $directory
        if (Test-Path -LiteralPath $path -PathType Container) {
            $files += @(Get-ChildItem -LiteralPath $path -Recurse -File |
                    Where-Object { $_.Extension -in '.c', '.h' })
        }
    }
    return $files
}

function Invoke-GitDiffCheck {
    $gitPath = (Get-Command git -ErrorAction Stop).Source
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $gitPath
    $startInfo.Arguments = "-C `"$ProjectRoot`" diff HEAD --check"
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    [void]$process.Start()
    $standardOutput = $process.StandardOutput.ReadToEnd()
    $standardError = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output = ($standardOutput + $standardError).Trim()
    }
}

function Test-MainUserCodeDiff {
    param([string]$MainRelativePath)

    $currentPath = Join-Path $ProjectRoot $MainRelativePath
    $currentLines = @(Get-Content -LiteralPath $currentPath -Encoding UTF8)
    $baseLines = @(& git -C $ProjectRoot show "HEAD:$($MainRelativePath -replace '\\','/')" 2>$null)

    function Get-AllowedLines {
        param([string[]]$Lines)

        $allowed = @{}
        $inside = $false
        for ($index = 0; $index -lt $Lines.Count; ++$index) {
            if ($Lines[$index] -match 'USER CODE BEGIN') {
                $inside = $true
            }
            $allowed[$index + 1] = $inside
            if ($Lines[$index] -match 'USER CODE END') {
                $inside = $false
            }
        }
        return $allowed
    }

    $currentAllowed = Get-AllowedLines $currentLines
    $baseAllowed = Get-AllowedLines $baseLines
    $diffLines = @(& git -C $ProjectRoot diff --unified=0 HEAD -- $MainRelativePath)
    $oldLine = 0
    $newLine = 0

    foreach ($line in $diffLines) {
        if ($line -match '^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@') {
            $oldLine = [int]$matches[1]
            $newLine = [int]$matches[2]
            continue
        }
        if ($line.StartsWith('+++') -or $line.StartsWith('---')) {
            continue
        }
        if ($line.StartsWith('+')) {
            if (-not $currentAllowed[$newLine]) {
                return $false
            }
            ++$newLine
            continue
        }
        if ($line.StartsWith('-')) {
            if (-not $baseAllowed[$oldLine]) {
                return $false
            }
            ++$oldLine
            continue
        }
        if ($line.StartsWith(' ')) {
            ++$oldLine
            ++$newLine
        }
    }
    return $true
}

Push-Location $ProjectRoot
try {
    $requiredFiles = @(
        'App\app_main.c', 'App\app_main.h', 'App\app_status.c', 'App\app_status.h',
        'App\app_config.h', 'App\app_version.h', 'BSP\bsp_led.c', 'BSP\bsp_led.h',
        'BSP\bsp_uart.c', 'BSP\bsp_uart.h', 'Common\software_timer.c',
        'Common\software_timer.h', 'Middleware\logger.c', 'Middleware\logger.h',
        'Services\health_service.c', 'Services\health_service.h',
        'Tests\Host\CMakeLists.txt', 'tools\test-host.ps1', 'docs\phase-01-firmware-foundation.md'
    )
    $missingFiles = @($requiredFiles | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $ProjectRoot $_) -PathType Leaf)
        })
    Add-Check '必需文件' ($missingFiles.Count -eq 0) `
        $(if ($missingFiles) { $missingFiles -join ', ' } else { '全部存在' })

    $mainRelativePath = if (Test-Path -LiteralPath (Join-Path $ProjectRoot 'Core\Src\main.c')) {
        'Core\Src\main.c'
    }
    else {
        'Src\main.c'
    }
    $mainText = Get-Content -LiteralPath (Join-Path $ProjectRoot $mainRelativePath) -Raw -Encoding UTF8
    Add-Check 'App_Init 接入' ($mainText -match '\bApp_Init\s*\(\s*HAL_GetTick\s*\(\s*\)\s*\)') `
        $mainRelativePath
    Add-Check 'App_RunOnce 接入' `
        ($mainText -match '\bApp_RunOnce\s*\(\s*HAL_GetTick\s*\(\s*\)\s*\)') $mainRelativePath

    $userFiles = Get-TextFiles @('App', 'BSP', 'Common', 'Middleware', 'Services')
    $delayHits = @($userFiles | Select-String -Pattern '\bHAL_Delay\s*\(')
    $delayHits += @(Select-String -LiteralPath (Join-Path $ProjectRoot $mainRelativePath) `
            -Pattern '\bHAL_Delay\s*\(')
    Add-Check '禁止 HAL_Delay' ($delayHits.Count -eq 0) `
        $(if ($delayHits) { '发现阻塞延时' } else { '未发现' })

    $logicFiles = Get-TextFiles @('App', 'Common', 'Middleware', 'Services')
    $halDependencyHits = @($logicFiles |
            Select-String -Pattern '#\s*include\s*"(?:stm32.*hal|main|usart)\.h"')
    Add-Check '逻辑层 HAL 解耦' ($halDependencyHits.Count -eq 0) `
        $(if ($halDependencyHits) { '发现 HAL/生成头依赖' } else { '依赖方向正确' })

    $loggerPath = Join-Path $ProjectRoot 'Middleware\logger.c'
    $loggerText = Get-Content -LiteralPath $loggerPath -Raw -Encoding UTF8
    Add-Check 'Logger UART 解耦' `
        ($loggerText -notmatch '(?i)bsp_uart|huart|HAL_UART|usart\.h') '仅依赖注入写函数'

    $algorithmFiles = Get-TextFiles @('Algorithms', 'Algorithm')
    $algorithmHalHits = @($algorithmFiles |
            Select-String -Pattern '(?i)stm32.*hal|main\.h|usart\.h')
    Add-Check '算法层 HAL 解耦' ($algorithmHalHits.Count -eq 0) `
        $(if ($algorithmHalHits) { '发现 HAL 依赖' } else { '未发现违规依赖' })

    $dynamicMemoryHits = @($userFiles |
            Select-String -Pattern '\b(?:malloc|calloc|realloc)\s*\(')
    Add-Check '禁止动态内存' ($dynamicMemoryHits.Count -eq 0) `
        $(if ($dynamicMemoryHits) { '发现动态分配调用' } else { '未发现' })

    $cmakeText = Get-Content -LiteralPath (Join-Path $ProjectRoot 'CMakeLists.txt') `
        -Raw -Encoding UTF8
    $userCmakePath = Join-Path $ProjectRoot 'cmake\user_sources.cmake'
    if (Test-Path -LiteralPath $userCmakePath) {
        $cmakeText += Get-Content -LiteralPath $userCmakePath -Raw -Encoding UTF8
    }
    $requiredSources = @(
        'app_main.c', 'app_status.c', 'bsp_led.c', 'bsp_uart.c',
        'software_timer.c', 'logger.c', 'health_service.c'
    )
    $missingSources = @($requiredSources | Where-Object { $cmakeText -notmatch [regex]::Escape($_) })
    Add-Check 'CMake 用户源码' ($missingSources.Count -eq 0) `
        $(if ($missingSources) { $missingSources -join ', ' } else { '全部接入' })

    $elfFiles = @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'build') -Recurse `
            -File -Filter '*.elf' -ErrorAction SilentlyContinue)
    $mapFiles = @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'build') -Recurse `
            -File -Filter '*.map' -ErrorAction SilentlyContinue)
    Add-Check 'ELF 产物' ($elfFiles.Count -gt 0) `
        $(if ($elfFiles) { $elfFiles[0].FullName } else { '未找到' })
    Add-Check 'MAP 产物' ($mapFiles.Count -gt 0) `
        $(if ($mapFiles) { $mapFiles[0].FullName } else { '未找到' })

    $trackedBuildFiles = @(& git -C $ProjectRoot ls-files |
            Where-Object { $_ -match '^(?:build|build-host)/' })
    Add-Check '构建目录未跟踪' ($trackedBuildFiles.Count -eq 0) `
        $(if ($trackedBuildFiles) { $trackedBuildFiles -join ', ' } else { '未跟踪' })

    $changedFiles = @(& git -C $ProjectRoot diff --name-only HEAD --)
    $forbiddenGeneratedChanges = @($changedFiles | Where-Object {
            $_ -match '^(?:Drivers/|cmake/stm32cubemx/|startup_.*\.s$|.*\.ld$|.*\.ioc2?$)' -or
            ($_ -match '^(?:Inc|Src)/' -and $_ -ne 'Src/main.c')
        })
    Add-Check 'CubeMX 生成文件保护' ($forbiddenGeneratedChanges.Count -eq 0) `
        $(if ($forbiddenGeneratedChanges) {
                $forbiddenGeneratedChanges -join ', '
            }
            else {
                '未修改受保护生成文件'
            })
    Add-Check 'main.c USER CODE 边界' (Test-MainUserCodeDiff $mainRelativePath) `
        '变更仅位于 USER CODE 区域'

    $diffCheck = Invoke-GitDiffCheck
    Add-Check 'Git 差异格式' ($diffCheck.ExitCode -eq 0) `
        $(if ($diffCheck.Output -and ($diffCheck.ExitCode -ne 0)) {
                $diffCheck.Output
            }
            else {
                '无行尾空白或补丁错误'
            })
}
finally {
    Pop-Location
}

if ($script:FailureCount -ne 0) {
    Write-Host "Phase 1 检查失败: $script:FailureCount 项" -ForegroundColor Red
    exit 1
}

Write-Host 'Phase 1 检查全部通过。' -ForegroundColor Green
exit 0
