# setup_voice_windows.ps1 - Instala e baixa a voz Kokoro pt-BR (opcional) no Windows.
# Requer espeak-ng (winget install --id eSpeak-NG.eSpeak-NG) e o backend preparado.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Error "Prepare o backend: scripts\test_auto.ps1"; exit 1 }
if (-not (Get-Command espeak-ng -ErrorAction SilentlyContinue)) {
  Write-Error "Instale o fonemizador: winget install --id eSpeak-NG.eSpeak-NG (e reabra o terminal)"; exit 1
}
& $Py -m pip install kokoro==0.9.4 transformers==4.57.6 soundfile==0.14.0 torch
$env:HF_HUB_DISABLE_XET = "1"
& $Py -c "from kokoro import KPipeline; p = KPipeline(lang_code='p', repo_id='hexgrad/Kokoro-82M', device='cpu'); p.load_voice('pf_dora')"
Write-Host "Voz Kokoro pt-BR pronta. Teste sem som: scripts\test_bancada.ps1 -Voz kokoro-file"
