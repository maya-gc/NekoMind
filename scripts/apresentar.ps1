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
# Supervisor: sobe Ollama/backend/bridge, reinicia o que cair, logs em backend\storage\logs
$sup = @("-m","app.devtools.supervisor","--porta",$Porta,"--voz",$Voz,"--modelo-tutor",$env:NEKOMIND_TUTOR_MODEL,"--abrir")
if (-not $env:NEKOMIND_TUTOR_MODEL) { $sup[7] = "qwen2.5:7b" }
if ($PlanoB) { $sup += "--plano-b" }
Write-Host "Operador: http://127.0.0.1:8000/presenter  |  Plateia: http://127.0.0.1:8000/public"
Write-Host "Placa: $Porta  |  Ctrl+C encerra tudo (backup do banco ao sair)."
try { & $Py @sup } finally { Pop-Location }
