# setup_espidf_portable.ps1 - Instala ESP-IDF e toolchains dentro do monorepo
# (nekomind\esp-idf e nekomind\tools), sem instalar nada globalmente.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_espidf_portable.ps1 [versao]
#   Ex.: ... setup_espidf_portable.ps1 v5.3.1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$EspIdfDir = Join-Path $Root "esp-idf"
$ToolsDir = Join-Path $Root "tools"
$env:IDF_TOOLS_PATH = $ToolsDir

$EspIdfVersion = if ($args.Count -gt 0) { $args[0] } else { "v5.3.1" }
$EspIdfRepo = "https://github.com/espressif/esp-idf.git"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "git nao encontrado. Instale o Git antes de prosseguir."
    exit 1
}

New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null

if (-not (Test-Path (Join-Path $EspIdfDir ".git"))) {
    Write-Host ">> Clonando ESP-IDF $EspIdfVersion em $EspIdfDir ..."
    git clone --depth 1 --branch $EspIdfVersion --recursive --shallow-submodules --jobs 8 $EspIdfRepo $EspIdfDir
} else {
    Write-Host ">> esp-idf ja presente em $EspIdfDir"
}

$InstallPs1 = Join-Path $EspIdfDir "install.ps1"
if (-not (Test-Path $InstallPs1)) {
    Write-Error "install.ps1 nao encontrado em $EspIdfDir"
    exit 1
}

Write-Host ">> Instalando toolchains em $IDF_TOOLS_PATH ..."
Push-Location $EspIdfDir
try {
    & $InstallPs1 esp32s3
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "== ESP-IDF instalado =="
Write-Host "  IDF_PATH       = $EspIdfDir"
Write-Host "  IDF_TOOLS_PATH = $ToolsDir"
Write-Host "  Ative com: . scripts\source_idf.ps1"