# Atualiza, grava o firmware e roda o teste de resistencia na placa.
# Funciona de qualquer pasta:
#   powershell -ExecutionPolicy Bypass -File C:\...\NekoMind\scripts\resistencia.ps1
#   ...\resistencia.ps1 -Minutos 10 -Porta COM3 -SemGravar
param([int]$Minutos = 60, [string]$Porta = "COM3", [switch]$SemGravar, [switch]$SemPull)
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
Write-Host ">> Teste de resistencia: $Minutos min" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m app.devtools.esp_tap_flow --port $Porta --minutos $Minutos
exit $LASTEXITCODE
