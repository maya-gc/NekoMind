# baixar_modelo_asr.ps1 - Instala faster-whisper e baixa o modelo de transcricao (uma vez).
# Depois disso tudo roda offline. Uso: scripts\baixar_modelo_asr.ps1 [-Modelo small]
param([string]$Modelo = "small")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Error "Prepare o backend: scripts\test_auto.ps1"; exit 1 }
& $Py -m pip install -q -r (Join-Path $Root "backend\requirements-real.txt")
$env:HF_HUB_DISABLE_XET = "1"
& $Py -c "from faster_whisper import WhisperModel; WhisperModel('$Modelo', device='cpu', compute_type='int8'); print('Modelo $Modelo pronto (cache local).')"
Write-Host "Teste: scripts\test_auto.ps1 -Asr whisper"
