# run_tests.ps1 - Executa os testes pytest do backend.
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
    & $Python -m pytest -v
} finally {
    Pop-Location
}