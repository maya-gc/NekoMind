# preparar_windows.ps1 - Deixa o Windows pronto para VOCE testar com voz, microfone e tutor IA.
# Instala (uma vez, com internet): Python 3.12 (Kokoro nao roda no 3.13), eSpeak NG,
# voz Kokoro pt-BR, Ollama + modelo do tutor e o modelo de transcricao.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\preparar_windows.ps1 [-ModeloTutor qwen2.5:7b]
param([string]$ModeloTutor = "qwen2.5:7b")
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new(); $env:PYTHONIOENCODING = "utf-8"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
function Passo($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Instalar($id) { winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements --scope user 2>$null; if ($LASTEXITCODE -ne 0) { winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements } }

Passo "Python 3.12"
& py -3.12 -c "import sys" 2>$null
if ($LASTEXITCODE -ne 0) { Instalar "Python.Python.3.12" }
$ver = if (Test-Path $Py) { & $Py -c "import sys;print(f'{sys.version_info[0]}.{sys.version_info[1]}')" } else { "" }
if ($ver -ne "3.12") {
  if (Test-Path $Venv) { Rename-Item $Venv ("$Venv-" + ($ver -replace '\.','') + "-" + (Get-Date -Format yyyyMMddHHmm)) }
  & py -3.12 -m venv $Venv
}
& $Py -m pip install -q --upgrade pip
& $Py -m pip install -q -r (Join-Path $Backend "requirements-dev.txt") -r (Join-Path $Backend "requirements-real.txt")

Passo "eSpeak NG (fonemas da voz) - aceite a janela de permissao se aparecer"
if (-not (Test-Path "$env:ProgramFiles\eSpeak NG\libespeak-ng.dll")) { Instalar "eSpeak-NG.eSpeak-NG" }

Passo "Voz Kokoro pt-BR"
& $Py -m pip install -q kokoro==0.9.4 transformers==4.57.6 soundfile==0.14.0 torch
$env:HF_HUB_DISABLE_XET = "1"
Push-Location $Backend
& $Py -c "from app.mac.speaker import KokoroSpeaker; from pathlib import Path; s=KokoroSpeaker(Path('storage/mac/speech'), play=False); s.preload(); s.close(); print('Kokoro OK')" 2>&1 | Select-Object -Last 3
Pop-Location
if ($LASTEXITCODE -ne 0) { Push-Location $Backend; & $Py -c "from kokoro import KPipeline; p=KPipeline(lang_code='p', repo_id='hexgrad/Kokoro-82M', device='cpu'); p.load_voice('pf_dora'); print('voz baixada')"; Pop-Location }

Passo "Ollama + modelo do tutor ($ModeloTutor)"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { Instalar "Ollama.Ollama"; $env:PATH += ";$env:LOCALAPPDATA\Programs\Ollama" }
Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
Start-Sleep 3
ollama pull $ModeloTutor

Passo "Modelo de transcricao"
& $Py -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('faster-whisper OK')"

Passo "Checklist"
Push-Location $Backend
$env:NEKOMIND_TUTOR_MODEL = $ModeloTutor
& $Py -m app.devtools.preflight --voz kokoro
Pop-Location
Write-Host "`nPronto. Para testar: scripts\testar_eu_mesma.ps1" -ForegroundColor Green
