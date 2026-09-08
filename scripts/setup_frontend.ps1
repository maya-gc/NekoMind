# setup_frontend.ps1 - Cria o venv do frontend Streamlit e instala dependencias.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$FrontDir = Join-Path $Root "frontend\streamlit"
$VenvDir = Join-Path $FrontDir ".venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"

Push-Location $FrontDir
try {
    if (-not (Test-Path $VenvDir)) {
        Write-Host ">> Criando venv em $VenvDir ..."
        python -m venv $VenvDir
    }

    Write-Host ">> Instalando dependencias ..."
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r requirements.txt

    Write-Host ""
    Write-Host "== Frontend pronto =="
    Write-Host "  Rode: . scripts\run_frontend.ps1"
} finally {
    Pop-Location
}