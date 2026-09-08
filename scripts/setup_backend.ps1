# setup_backend.ps1 - Cria o venv do backend e instala dependencias.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"

Push-Location $BackendDir
try {
    if (-not (Test-Path $VenvDir)) {
        Write-Host ">> Criando venv em $VenvDir ..."
        python -m venv $VenvDir
    }

    Write-Host ">> Instalando dependencias ..."
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r requirements.txt

    Write-Host ""
    Write-Host "== Backend pronto =="
    Write-Host "  Ative: .\$VenvDir\Scripts\Activate.ps1"
    Write-Host "  Rode:  . scripts\run_backend.ps1"
} finally {
    Pop-Location
}