# test_bancada.ps1 - Pipeline MANUAL de bancada (Windows): voce toca no display.
# Abre o backend numa janela e o bridge nesta janela, ligados a placa pela USB.
# Padrao: microfone real + voz Kokoro no alto-falante (se instalada).
#   -Voz silent        -> nao toca audio (falas ficam registradas em texto)
#   -Voz off           -> sem voz
#   -AudioArquivo a.wav,b.wav -> usa WAVs no lugar do microfone
# Uso: powershell -ExecutionPolicy Bypass -File scripts\test_bancada.ps1 -Porta COM3
param([string]$Porta = "", [ValidateSet("kokoro","kokoro-file","silent","off")][string]$Voz = "kokoro",
      [string[]]$AudioArquivo = @())
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Write-Error "Rode antes: scripts\test_auto.ps1 (cria o ambiente)"; exit 1 }
if (-not $Porta) {
  $Porta = & $Py -c "from serial.tools import list_ports as l; p=[x.device for x in l.comports() if x.vid==0x303A]; print(p[0] if p else '')"
  if (-not $Porta) { Write-Error "Placa ESP nao encontrada. Informe -Porta COMx."; exit 1 }
}
Write-Host ">> Placa em $Porta. Subindo backend em http://127.0.0.1:8000 ..."
$srv = Start-Process -FilePath $Py -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory $Backend -PassThru
Start-Sleep 4
Write-Host ">> Operador: http://127.0.0.1:8000/presenter   Plateia: http://127.0.0.1:8000/public"
$bargs = @("-m","app.mac","--port",$Porta,"--voice",$Voz)
foreach ($f in $AudioArquivo) { $bargs += @("--audio-file", (Resolve-Path $f).Path) }
Push-Location $Backend
try {
  if ($Voz -eq "kokoro") {
    & $Py -c "import kokoro" 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Warning "Kokoro nao instalado (scripts\setup_voice_windows.ps1). Usando -Voz silent."; $bargs[5] = "silent" }
  }
  Write-Host ">> Bridge ativo. Toque no display. Ctrl+C encerra."
  & $Py @args
} finally {
  Pop-Location
  Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue
}
