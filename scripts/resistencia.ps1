# Atualiza, grava o firmware e testa a placa. Funciona de qualquer pasta:
#   powershell -ExecutionPolicy Bypass -File C:\...\NekoMind\scripts\resistencia.ps1
#     padrao: teste RAPIDO (~3 min): 8 fluxos completos + rajada de 300
#     quadros no USB + saude do firmware (quadro do avatar e pilha)
#   ...\resistencia.ps1 -Minutos 60      # resistencia longa (vespera)
#   ...\resistencia.ps1 -SemGravar       # so testa (firmware ja gravado)
param([int]$Minutos = 0, [string]$Porta = "COM3", [switch]$SemGravar, [switch]$SemPull)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
if (-not $SemPull) {
  Write-Host ">> git pull" -ForegroundColor Cyan
  git pull --ff-only
  if ($LASTEXITCODE -ne 0) { throw "git pull falhou" }
}
if (-not $SemGravar) {
  Write-Host ">> Gravando firmware em $Porta" -ForegroundColor Cyan
  & (Join-Path $raiz "scripts\firmware.ps1") -Gravar -Porta $Porta
  if ($LASTEXITCODE -ne 0) { throw "gravacao do firmware falhou" }
  Start-Sleep -Seconds 4   # placa reiniciando
}
Set-Location (Join-Path $raiz "backend")
if ($Minutos -gt 0) {
  Write-Host ">> Teste de resistencia: $Minutos min" -ForegroundColor Cyan
  & .\.venv\Scripts\python.exe -m app.devtools.esp_tap_flow --port $Porta --minutos $Minutos
} else {
  Write-Host ">> Teste rapido (~3 min)" -ForegroundColor Cyan
  & .\.venv\Scripts\python.exe -m app.devtools.esp_tap_flow --port $Porta --rapido
}
exit $LASTEXITCODE
