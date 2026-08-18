[CmdletBinding()]
param(
    [string]$Port = 'COM4',
    [ValidateRange(1200, 3000000)][int]$Baud = 115200
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = Join-Path $root 'host'

Write-Host 'Phase 10 最终 600 秒验收即将开始。此窗口会显示总计时和每阶段倒计时。' -ForegroundColor Cyan
python .\host\phase10_system_acceptance.py --port $Port --baud $Baud `
    --output .\artifacts\phase10\final-validation
$result = $LASTEXITCODE
if ($result -eq 0) {
    Write-Host 'Phase 10 600 秒真实硬件验收完成。' -ForegroundColor Green
} else {
    Write-Host "Phase 10 验收失败，退出码：$result" -ForegroundColor Red
}
Read-Host '按 Enter 关闭此窗口'
exit $result
