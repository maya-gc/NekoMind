# run_all.ps1 - Inicia backend e frontend em processos separados.
# Exibe URLs e salva logs em logs\ na raiz do repositorio.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

Write-Host ">> Iniciando backend em http://127.0.0.1:8000 ..."
$Backend = Start-Process -FilePath powershell -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","$(Join-Path $PSScriptRoot 'run_backend.ps1')" -RedirectStandardOutput (Join-Path $LogDir "backend.log") -RedirectStandardError (Join-Path $LogDir "backend.err.log") -PassThru -WindowStyle Hidden

Write-Host ">> Iniciando frontend em http://127.0.0.1:8501 ..."
$Frontend = Start-Process -FilePath powershell -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","$(Join-Path $PSScriptRoot 'run_frontend.ps1')" -RedirectStandardOutput (Join-Path $LogDir "frontend.log") -RedirectStandardError (Join-Path $LogDir "frontend.err.log") -PassThru -WindowStyle Hidden

Write-Host ""
Write-Host "== URLs =="
Write-Host "  Backend:  http://127.0.0.1:8000  (docs: /docs)"
Write-Host "  Frontend: http://127.0.0.1:8501"
Write-Host "  Logs:     $LogDir"
Write-Host ""
Write-Host "PIDs: backend=$($Backend.Id) frontend=$($Frontend.Id)"
Write-Host "Para encerrar: . scripts\stop_all.ps1 (ou use o Gerenciador de Tarefas)"