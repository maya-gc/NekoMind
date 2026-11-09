# firmware.ps1 - Compila (e opcionalmente grava) o firmware do ESP32-S3 no Windows.
#   powershell -ExecutionPolicy Bypass -File scripts\firmware.ps1            # so compila
#   powershell -ExecutionPolicy Bypass -File scripts\firmware.ps1 -Gravar -Porta COM3
# Procura o ESP-IDF em: $env:IDF_PATH, .\esp-idf, ~\.espressif\idf-env.json.
param([switch]$Gravar, [string]$Porta = "", [string]$IdfPath = "")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Fw = Join-Path $Root "iot\nekomind_firmware"
$cands = @($IdfPath, $env:IDF_PATH, (Join-Path $Root "esp-idf"))
$envJson = Join-Path $env:USERPROFILE ".espressif\idf-env.json"
if (Test-Path $envJson) {
  $j = Get-Content $envJson -Raw | ConvertFrom-Json
  foreach ($p in $j.idfInstalled.PSObject.Properties) { $cands += $p.Value.path }
}
$Idf = $cands | Where-Object { $_ -and (Test-Path (Join-Path $_ "export.ps1")) } | Select-Object -First 1
if (-not $Idf) { Write-Error "ESP-IDF nao encontrado. Rode scripts\setup_espidf_portable.ps1 ou informe -IdfPath."; exit 1 }
Write-Host ">> ESP-IDF: $Idf"
$env:IDF_PATH = $Idf
. (Join-Path $Idf "export.ps1") | Out-Null
Push-Location $Fw
try {
  if (-not (Test-Path "sdkconfig")) { idf.py set-target esp32s3 }
  idf.py build
  if ($LASTEXITCODE -ne 0) { Write-Error "Falha na compilacao"; exit 1 }
  Write-Host "RESULTADO: COMPILOU"
  if ($Gravar) {
    if (-not $Porta) { Write-Error "Informe -Porta COMx para gravar"; exit 1 }
    idf.py -p $Porta flash
    if ($LASTEXITCODE -ne 0) { Write-Error "Falha ao gravar"; exit 1 }
    Write-Host "RESULTADO: GRAVADO em $Porta"
  }
} finally { Pop-Location }
