# apresentar.ps1 - Modo apresentacao (Windows): checklist, backend, bridge e telas.
#   powershell -ExecutionPolicy Bypass -File scripts\apresentar.ps1            # modo real
#   powershell -ExecutionPolicy Bypass -File scripts\apresentar.ps1 -PlanoB    # demo identificado
#   ... -Porta COM3 -Voz silent     (sem alto-falante)
param([string]$Porta = "", [ValidateSet("kokoro","kokoro-file","silent","off")][string]$Voz = "kokoro",
      [switch]$PlanoB, [switch]$Forcar, [string]$Modelo = "small")
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new(); $env:PYTHONIOENCODING = "utf-8"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Error "Prepare antes: scripts\test_auto.ps1"; exit 1 }

function Test-LocalUrl([string]$Url) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
    return $response.StatusCode -eq 200
  } catch { return $false }
}

function Get-RunningSupervisor {
  $escapedRoot = [Regex]::Escape($Root)
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
      $_.Name -match '^python(\.exe)?$' -and
      $_.CommandLine -match 'app\.devtools\.supervisor' -and
      $_.CommandLine -match $escapedRoot
    } |
    Select-Object -First 1
}

function Start-StreamlitIfAvailable {
  if (Test-LocalUrl "http://127.0.0.1:8501") { return $true }
  $frontPy = Join-Path $Root "frontend\streamlit\.venv\Scripts\python.exe"
  if (-not (Test-Path $frontPy)) {
    Write-Warning "Painel Streamlit ainda nao preparado. Rode scripts\setup_frontend.ps1 se precisar dele."
    return $false
  }
  $logDir = Join-Path $Backend "storage\logs"
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $PSScriptRoot "run_frontend.ps1")
  ) -WorkingDirectory $Root `
    -RedirectStandardOutput (Join-Path $logDir "streamlit-current.out.log") `
    -RedirectStandardError (Join-Path $logDir "streamlit-current.err.log") | Out-Null
  return $true
}

# O atalho pode ser executado mais de uma vez. Se a instancia desta copia do
# projeto ja estiver saudavel, nao disputa a porta HTTP nem a serial do ESP.
$runningSupervisor = Get-RunningSupervisor
if ($runningSupervisor -and (Test-LocalUrl "http://127.0.0.1:8000/health")) {
  Start-StreamlitIfAvailable | Out-Null
  Write-Host "NekoMind ja esta rodando (supervisor PID $($runningSupervisor.ProcessId))."
  Write-Host "Operador: http://127.0.0.1:8000/presenter"
  Write-Host "Plateia:  http://127.0.0.1:8000/public"
  Write-Host "Touch:    http://127.0.0.1:8000/touch"
  if (Test-LocalUrl "http://127.0.0.1:8501") {
    Write-Host "Painel:   http://127.0.0.1:8501"
  }
  if (-not $env:NEKOMIND_NO_BROWSER) {
    Start-Process "http://127.0.0.1:8000/presenter"
    Start-Process "http://127.0.0.1:8000/public"
  }
  exit 0
}

Push-Location $Backend
$json = Join-Path $Backend "storage\preflight.json"
$pf = @("-m","app.devtools.preflight","--voz",$Voz,"--modelo",$Modelo,"--json",$json)
if ($Porta) { $pf += @("--porta",$Porta) }
if ($PlanoB) { $pf += "--plano-b" }
& $Py @pf
if ($LASTEXITCODE -ne 0 -and -not $Forcar) { Write-Host "`nCorrija os itens acima, use -PlanoB ou -Forcar."; Pop-Location; exit 1 }
$pfj = Get-Content $json -Raw | ConvertFrom-Json
if (-not $Porta) { $Porta = $pfj.porta }
$vozItem = $pfj.itens | Where-Object { $_.item -eq "Voz da gatinha" }
if ($Voz -eq "kokoro" -and $vozItem.status -ne "ok") { Write-Warning "Voz Kokoro indisponivel; seguindo sem som (rode scripts\preparar_windows.ps1)."; $Voz = "silent" }
if (-not $Porta) { Write-Error "Placa nao encontrada."; Pop-Location; exit 1 }
Start-StreamlitIfAvailable | Out-Null
# Supervisor: sobe Ollama/backend/bridge, reinicia o que cair, logs em backend\storage\logs
$sup = @("-m","app.devtools.supervisor","--porta",$Porta,"--voz",$Voz,"--modelo-tutor",$env:NEKOMIND_TUTOR_MODEL,"--abrir")
if (-not $env:NEKOMIND_TUTOR_MODEL) { $sup[7] = "qwen2.5:7b" }
if ($PlanoB) { $sup += "--plano-b" }
Write-Host "Operador: http://127.0.0.1:8000/presenter  |  Plateia: http://127.0.0.1:8000/public"
Write-Host "Placa: $Porta  |  Ctrl+C encerra tudo (backup do banco ao sair)."
try { & $Py @sup } finally { Pop-Location }
