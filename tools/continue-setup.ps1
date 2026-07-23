[CmdletBinding()]
param()

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Write-Host '重新检测 STM32 VS Code 环境。'
& (Join-Path $PSScriptRoot 'diagnose-stm32-env.ps1')
Write-Host ''
Write-Host '如果 STM32CubeMX 尚未安装，请从 STMicroelectronics 官方网站安装并接受许可协议。'
Write-Host 'CubeMX 生成工程后，再运行 tools\diagnose-stm32-env.ps1 和 tools\build.ps1。'
