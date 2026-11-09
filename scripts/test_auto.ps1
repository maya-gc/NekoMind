# test_auto.ps1 - Pipeline AUTOMATICA e silenciosa (Windows).
# Sem alto-falante, sem microfone e sem tocar no display:
#   1. testes do backend (pytest)       2. testes do frontend (node)
#   3. pipeline ponta a ponta com toque virtual + voz do Windows (SAPI)
#   4. teste de fumaca da placa ESP pela USB (pulado se nao houver placa)
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\test_auto.ps1 [-Asr whisper] [-SemPlaca]
param([ValidateSet("roteiro","whisper")][string]$Asr = "roteiro", [switch]$SemPlaca, [string]$Porta = "")
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONWARNINGS = "ignore::DeprecationWarning"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"
$Out = Join-Path $Backend ("storage\pipeline\" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force $Out | Out-Null
$Resumo = Join-Path $Out "00_resumo.txt"
function Res($n, $ok, $d) { $l = "{0,-30} {1}  {2}" -f $n, $(if ($ok) { "OK   " } else { "FALHA" }), $d; $l | Tee-Object -FilePath $Resumo -Append }

if (-not (Test-Path $Py)) {
  Write-Host ">> Criando ambiente Python do backend..."
  $cmd = "python"; $a = @()
  foreach ($v in "-3.12", "-3.11", "-3.13") { & py $v -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { $cmd = "py"; $a = @($v); break } }
  & $cmd @a -m venv (Join-Path $Backend ".venv")
}
Write-Host ">> Conferindo dependencias..."
& $Py -m pip install -q -r (Join-Path $Backend "requirements-test.txt") *> (Join-Path $Out "01_pip.txt")

Push-Location $Backend
& $Py -m pytest -q -rfEs -p no:cacheprovider *> (Join-Path $Out "02_pytest.txt"); $ok = $LASTEXITCODE -eq 0
Res "Backend (pytest)" $ok ((Get-Content (Join-Path $Out "02_pytest.txt") | Select-Object -Last 1))
Pop-Location

Push-Location $Root
if (Get-Command node -ErrorAction SilentlyContinue) {
  $files = (Get-ChildItem frontend\tests\*.test.mjs).FullName
  node --test $files *> (Join-Path $Out "03_frontend.txt"); $ok = $LASTEXITCODE -eq 0
  Res "Frontend (node --test)" $ok ((Select-String -Path (Join-Path $Out "03_frontend.txt") -Pattern "(pass|fail) \d+" | ForEach-Object { $_.Line.Trim() }) -join " ")
} else { Res "Frontend (node --test)" $false "Node.js nao instalado" }
Pop-Location

Push-Location $Backend
& $Py -m app.devtools.pipeline --asr $Asr --out (Join-Path $Out "pipeline") *> (Join-Path $Out "04_pipeline.txt"); $ok = $LASTEXITCODE -eq 0
Res "Pipeline toque virtual" $ok ((Select-String -Path (Join-Path $Out "04_pipeline.txt") -Pattern "RESULTADO" | ForEach-Object { $_.Line }) -join " ")
if (-not $SemPlaca) {
  $pa = @(); if ($Porta) { $pa = @("--port", $Porta) }
  & $Py -m app.devtools.esp_probe @pa *> (Join-Path $Out "05_placa.txt"); $ok = $LASTEXITCODE -eq 0
  Res "Placa ESP (USB)" $ok ((Select-String -Path (Join-Path $Out "05_placa.txt") -Pattern "RESULTADO" | ForEach-Object { $_.Line }) -join " ")
}
Pop-Location
Write-Host ""
Write-Host "Logs e relatorio: $Out"
