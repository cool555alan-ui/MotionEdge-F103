[CmdletBinding(SupportsShouldProcess)]
param()

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$allowed = @()
$build = Join-Path $ProjectRoot 'build'
if (Test-Path -LiteralPath $build -PathType Container) { $allowed += Get-Item -LiteralPath $build }
$allowed += @(Get-ChildItem -LiteralPath $ProjectRoot -Directory -Filter 'cmake-build-*' -ErrorAction SilentlyContinue)

if ($allowed.Count -eq 0) {
    Write-Host '没有可清理的 build 或 cmake-build-* 目录。'
    exit 0
}

foreach ($directory in $allowed) {
    $resolved = $directory.FullName
    if (-not $resolved.StartsWith($ProjectRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝清理项目目录之外的路径: $resolved"
    }
    if ($PSCmdlet.ShouldProcess($resolved, '删除构建输出目录')) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
        Write-Host "已清理: $resolved"
    }
}
