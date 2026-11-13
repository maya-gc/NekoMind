# Pipelines de teste — Windows e macOS

Atualizado em 09/11/2026 (segunda rodada: CI, 7 cenários, toque no firmware). O projeto roda no **macOS** (onde foi validado na
bancada) e no **Windows**. O caminho do Mac não mudou: `afplay`, `caffeinate`,
`fcntl`, `O_NOFOLLOW` e a permissão `0600` do token continuam iguais. As
diferenças de sistema ficam isoladas em `backend/app/platform_support.py`.

Há duas pipelines com objetivos diferentes:

| | Automática (silenciosa) | Bancada (manual) |
|---|---|---|
| Para quê | Desenvolvimento diário, regressão, CI local | Ensaio real com pessoas |
| Toque no LCD | **Virtual**: mesmas mensagens JSON Lines do firmware | Você toca no display |
| Fala do estudante | **Voz do sistema** (SAPI no Windows, `say` no Mac) gravada em WAV | Microfone real |
| Voz da gatinha | **Silenciosa**: o texto fica registrado, nada toca | Kokoro no alto-falante |
| Placa ESP | Teste de fumaça pela USB (heartbeat + `display_ack`) | Fluxo completo na placa |
| Comando Windows | `scripts\test_auto.ps1` | `scripts\test_bancada.ps1 -Porta COM3` |
| Comando macOS | `bash scripts/test_auto.sh` | `bash scripts/test_bancada.sh /dev/cu.usbmodem…` |

## Visão geral

```text
           ┌── CI GitHub (Windows + macOS, a cada push) ──────────────────────┐
           │ pytest · node --test · firmware em C · pipeline 7 cenários       │
           └──────────────────────────────────────────────────────────────────┘
 test_auto ─ pytest ─ frontend ─ pipeline (toque virtual) ─ firmware C ─ placa USB
 esp_tap_flow ─ toques simulados DENTRO do firmware (!tap) ─ LCD real ─ bridge real
 test_bancada / apresentar ─ pessoa tocando, microfone e voz reais
```

## Pipeline automática

```powershell
# Windows (PowerShell, na raiz do projeto)
powershell -ExecutionPolicy Bypass -File scripts\test_auto.ps1            # ASR por roteiro
powershell -ExecutionPolicy Bypass -File scripts\test_auto.ps1 -Asr whisper
powershell -ExecutionPolicy Bypass -File scripts\test_auto.ps1 -SemPlaca
```

```bash
# macOS
bash scripts/test_auto.sh                 # --asr whisper | --sem-placa | --porta /dev/cu...
```

Etapas, com log em `backend/storage/pipeline/<data-hora>/`:

1. `pytest` do backend (inclui `tests/test_platform_and_devtools.py`).
2. Testes do frontend (`node --test`).
3. `python -m app.devtools.pipeline` — ponta a ponta no mesmo processo, com
   banco SQLite temporário (não toca nos seus dados):
   - **demo**: Diagnóstico → Começar → Pausar → Continuar → Finalizar → resultado → Voltar;
   - **guiado** (modo real): operador salva o material “Ciclo da água” →
     Diagnóstico → missões no touch → Começar (missão 1) → 1ª resposta →
     **pergunta** → Pedir dica → Responder → 2ª resposta → **comparação**;
   - **longo**: 5 pontos → 5 missões; a pergunta é sobre a missão 4 escolhida;
   - **errada**: resposta sem relação com o material não inventa cobertura;
   - **silencio**: 3 s de silêncio viram **erro claro** (nunca resultado);
   - **ruido**: resposta com ruído vira resultado ou erro com código;
   - **queda_usb**: o cabo “cai” durante a gravação → recuperação → Retomar →
     resultado.

   Opções: `--cenario X` (repetível), `--repeticoes N` (taxa de sucesso por
   etapa), `--capturas` (fotos de `/public` e `/touch` em cada etapa, usando
   Edge/Chrome já instalados), `--tempo-estrito` (etapa acima do orçamento de
   tempo falha), `--asr whisper`.
4. `python -m app.devtools.c_compiler` — testes do firmware em C no computador.
   Usa `cc`/`gcc`/`clang` ou o clang do pacote `ziglang` (Windows sem MSYS2).
5. `python -m app.devtools.esp_probe` — se a placa estiver na USB, confirma o
   heartbeat do firmware e que o LCD redesenhou (`draw_ok`). Não grava firmware.

### Fluxo completo na placa com toques simulados

`python -m app.devtools.esp_tap_flow --port COM3` (Mac: `--port /dev/cu.…`).
Com o firmware de 09/11/2026 gravado (`scripts\firmware.ps1 -Gravar -Porta COM3`),
o computador envia `!tap diagnose`, `!tap start`… e **o próprio firmware**
executa o toque: mesmo hit test de um dedo, só em botões visíveis e habilitados.
Cada etapa espera o `display_ack` da tela desenhada. O resto da cadeia é real.
`!tap 120 260` também aceita coordenadas.

### Teste rápido da placa (~3 min) e resistência

```powershell
powershell -ExecutionPolicy Bypass -File scripts\resistencia.ps1              # rápido: pull + grava + 8 fluxos + rajada USB
powershell -ExecutionPolicy Bypass -File scripts\resistencia.ps1 -Minutos 60  # longo (véspera)
```

O rápido envia ainda 300 quadros seguidos pelo USB e confirma que a placa
continua respondendo (pega de volta o defeito do “Write timeout”).

### Teste de resistência (1 hora na placa)

```powershell
cd backend
.venv\Scripts\python.exe -m app.devtools.esp_tap_flow --port COM3 --minutos 60
```

Repete o fluxo guiado até completar o tempo e lê a linha `saude:` que o
firmware imprime a cada 30 s. Reprova se algum quadro do avatar 3D passar de
**60 ms** ou se a pilha livre da tarefa cair abaixo de **2048 bytes**. O
firmware também ajusta sozinho o ritmo do avatar (125 → 250 → 500 ms) quando
o desenho fica lento, para o toque e a serial nunca ficarem esperando, e tem
*watchdog* de 5 s (se a tarefa travar, a placa reinicia em vez de congelar).

### Sua própria voz

```powershell
.venv\Scripts\python.exe -m app.devtools.gravar_voz          # grava 4 respostas suas
.venv\Scripts\python.exe -m app.devtools.pipeline --asr whisper --cenario voz_real
```

Os WAVs ficam em `backend/storage/voz_real/` (fora do Git). Grave uma vez em
silêncio e outra com barulho (renomeie a pasta entre as rodadas) para comparar
a transcrição.

### ASR real

`scripts\baixar_modelo_asr.ps1` (ou `.sh`) uma vez, depois
`python -m app.devtools.pipeline --asr whisper`. O áudio da voz do sistema passa
pelo faster-whisper de verdade; o orçamento de tempo é ampliado.

### CI

Todo arquivo `iot/nekomind_firmware/tests/test_*.c` novo entra sozinho no
`python -m app.devtools.c_compiler` (Windows e macOS). Um job separado compila
o firmware inteiro com o ESP-IDF v5.3 (esp32s3) a cada push.


`.github/workflows/testes.yml` roda em `windows-latest` e `macos-latest` a cada
push na `main` e em PRs. O relatório da pipeline fica nos artefatos do run.

Relatório: `pipeline/relatorio.md` (tabela de etapas, falas da gatinha) e
`relatorio.json`; o tráfego serial virtual fica em `*/serial.jsonl` e os WAV da
voz do sistema em `pipeline/audio/`.

### O que é real e o que é simulado

| Peça | Na pipeline automática |
|---|---|
| Protocolo serial, bridge, API, SQLite, análise, diálogo de duas respostas | **Real** (mesmo código da bancada) |
| VAD (WebRTC) | **Real** quando `webrtcvad` está instalado: valida que o WAV da voz do sistema contém fala |
| ASR | `roteiro` (padrão): devolve o texto conhecido da resposta, rápido e sem modelo. `whisper`: transcreve o WAV com faster-whisper (exige modelo local) |
| Toque | Virtual (`app/devtools/virtual_touch.py`); não exercita o hardware de toque XPT2046 |
| Alto-falante / microfone | Não usados |

A pipeline mede o **fluxo**, não a qualidade pedagógica nem a acurácia do ASR
em vozes reais. Esses pontos continuam na bancada.

## Pipeline de bancada (manual)

```powershell
# Windows: backend + bridge, microfone real e voz Kokoro (se instalada)
powershell -ExecutionPolicy Bypass -File scripts\test_bancada.ps1 -Porta COM3
# sem alto-falante:  -Voz silent   (ou -Voz kokoro-file para só gerar os WAV)
# sem microfone:     -AudioArquivo resposta1.wav,resposta2.wav
```

```bash
# macOS
bash scripts/test_bancada.sh /dev/cu.usbmodem1101 kokoro
```

Abra `http://127.0.0.1:8000/presenter` (operador) e `/public` (plateia) e siga
o [roteiro mínimo do handoff](handoff-colaborador.md#roteiro-mínimo-de-verificação).

Opções novas do bridge (`python -m app.mac`):

- `--voice kokoro | kokoro-file | silent | off` — `kokoro-file` sintetiza e
  guarda `fala-NNN.wav` sem tocar; `silent` só registra `falas.jsonl`.
- `--audio-file X.wav` (repetível) — usa arquivos no lugar do microfone; a
  1ª sessão consome o 1º arquivo, a 2ª o 2º, e o último se repete.

Voz Kokoro no Windows: `winget install --id eSpeak-NG.eSpeak-NG` e depois
`scripts\setup_voice_windows.ps1`. No Mac continua `scripts/setup_voice_mac.sh`.

## Limites conhecidos

- O toque virtual da pipeline fala com o bridge; o toque **dentro** do
  firmware (`!tap`) exige a placa com o firmware de 09/11/2026.
- `!tap` é um comando de depuração aceito pela serial; não altera o protocolo
  JSON e não envia nada ao computador por conta própria.
- `tests/test_mac_serial.py` usa pseudo-terminal POSIX e é pulado no Windows.
- Testes que criam links simbólicos são pulados no Windows sem Modo de
  Desenvolvedor.
- No Windows, `pip install ziglang` (já em `requirements-dev.txt`) fornece o
  compilador C dos testes do firmware.
