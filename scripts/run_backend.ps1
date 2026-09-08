# run_backend.ps1 - Sobe a API FastAPI do NekoMind em http://127.0.0.1:8000
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Venv nao encontrado. Execute antes: . scripts\setup_backend.ps1"
    exit 1
}

Push-Location $BackendDir
try {
    & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
} finally {
    Pop-Location
}