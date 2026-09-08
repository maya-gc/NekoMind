# source_idf.ps1 - Configura o ambiente ESP-IDF na sessao PowerShell.
#
# Uso:
#   . scripts\source_idf.ps1
#   cd iot\nekomind_firmware; idf.py build
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$env:IDF_PATH = Join-Path $Root "esp-idf"
$env:IDF_TOOLS_PATH = Join-Path $Root "tools"

$ExportPs1 = Join-Path $env:IDF_PATH "export.ps1"
if (-not (Test-Path $ExportPs1)) {
    Write-Host "AVISO: $ExportPs1 nao encontrado." -ForegroundColor Yellow
    Write-Host "Execute antes: . scripts\setup_espidf_portable.ps1"
    exit 1
}

& $ExportPs1

Write-Host "== Ambiente ESP-IDF pronto =="
Write-Host "  IDF_PATH=$env:IDF_PATH"
Write-Host "  IDF_TOOLS_PATH=$env:IDF_TOOLS_PATH"