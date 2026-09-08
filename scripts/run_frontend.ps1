# run_frontend.ps1 - Sobe o dashboard Streamlit em http://127.0.0.1:8501
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$FrontDir = Join-Path $Root "frontend\streamlit"
$Python = Join-Path $FrontDir ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Venv nao encontrado. Execute antes: . scripts\setup_frontend.ps1"
    exit 1
}

Push-Location $FrontDir
try {
    & $Python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
} finally {
    Pop-Location
}