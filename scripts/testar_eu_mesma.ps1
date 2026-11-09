# testar_eu_mesma.ps1 - Teste manual completo: VOCE toca no display, fala no microfone
# e ouve a gatinha. Pergunta/dica/comparacao pelo tutor IA local (Ollama) quando disponivel.
#   powershell -ExecutionPolicy Bypass -File scripts\testar_eu_mesma.ps1 [-Porta COM3] [-SemVoz]
param([string]$Porta = "", [switch]$SemVoz, [string]$ModeloTutor = "qwen2.5:7b")
$env:NEKOMIND_TUTOR_PROVIDER = "auto"; $env:NEKOMIND_TUTOR_MODEL = $ModeloTutor
if (Get-Command ollama -ErrorAction SilentlyContinue) { Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue }
$voz = if ($SemVoz) { "silent" } else { "kokoro" }
$a = @("-Voz", $voz); if ($Porta) { $a += @("-Porta", $Porta) }
& (Join-Path $PSScriptRoot "apresentar.ps1") @a
