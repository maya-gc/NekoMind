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
if ($PlanoB) { $env:NEKOMIND_MODE="demo"; $env:NEKOMIND_ASR_PROVIDER="mock"; $env:NEKOMIND_LLM_PROVIDER="mock"; $extra=@("--simulate") }
else { $env:NEKOMIND_MODE="real"; $env:NEKOMIND_ASR_PROVIDER="faster_whisper"; $env:NEKOMIND_LLM_PROVIDER="local_keywords"; $env:NEKOMIND_ASR_MODEL_SIZE=$Modelo; $extra=@() }
$srv = Start-Process -FilePath $Py -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory $Backend -PassThru -WindowStyle Minimized
for ($i = 0; $i -lt 30; $i++) { try { Invoke-WebRequest "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 1 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 } }
Start-Process "http://127.0.0.1:8000/presenter"; Start-Process "http://127.0.0.1:8000/public"
Write-Host "Operador: http://127.0.0.1:8000/presenter  |  Plateia: http://127.0.0.1:8000/public"
Write-Host "Placa: $Porta  |  Ctrl+C encerra tudo."
try { & $Py -m app.mac --port $Porta --voice $Voz @extra }
finally { Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue; Pop-Location }
