# launch_vscode.ps1 - Abre o workspace nekomind no VS Code portatil.
$ErrorActionPreference = "Stop"

# 1. Raiz do repositorio (este script fica em <raiz>\scripts).
$Root = Split-Path -Parent $PSScriptRoot

# 2. Ambiente ESP-IDF (nao fatal se ainda nao instalado).
$env:IDF_PATH = Join-Path $Root "esp-idf"
$env:IDF_TOOLS_PATH = Join-Path $Root "tools"
$ExportPs1 = Join-Path $env:IDF_PATH "export.ps1"
if (Test-Path $ExportPs1) {
    try { & $ExportPs1 | Out-Null } catch { }
}

# 3. Localizar o binario do VS Code portatil.
$VsCodeBin = Get-ChildItem -Path (Join-Path $Root "vscode-portable") -Filter "Code.exe" -Recurse -Depth 3 -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName

if (-not $VsCodeBin -or -not (Test-Path $VsCodeBin)) {
    Write-Error "VS Code portatil nao encontrado em $Root\vscode-portable"
    Write-Host "Baixe e extraia em vscode-portable\ (ver vscode-portable\README.md)."
    exit 1
}

Write-Host ">> Abrindo workspace no VS Code portatil: $VsCodeBin"
& $VsCodeBin $Root