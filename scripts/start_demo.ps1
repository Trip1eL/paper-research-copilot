[CmdletBinding()]
param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot "frontend"
$frontendBuild = Join-Path $frontendRoot "dist\index.html"

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "未找到 npm。请先安装 Node.js 20 或更高版本。"
}

if (-not (Get-Command paper-research-api.exe -ErrorAction SilentlyContinue)) {
    throw "未找到 paper-research-api。请激活 Conda 环境并执行 python -m pip install -e `".[dev]`"。"
}

Push-Location $frontendRoot
try {
    if (-not $SkipBuild) {
        if (-not (Test-Path (Join-Path $frontendRoot "node_modules"))) {
            & npm.cmd ci
            if ($LASTEXITCODE -ne 0) {
                throw "npm ci 执行失败。"
            }
        }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) {
            throw "前端生产构建失败。"
        }
    }
} finally {
    Pop-Location
}

if (-not (Test-Path $frontendBuild)) {
    throw "未找到 frontend/dist/index.html。请移除 -SkipBuild 或先执行 npm run build。"
}

Write-Host "Paper Research Copilot: http://127.0.0.1:8000"
Write-Host "OpenAPI: http://127.0.0.1:8000/docs"
& paper-research-api.exe
