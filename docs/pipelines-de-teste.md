# Pipelines de teste — Windows e macOS

Atualizado em 09/11/2026. O projeto roda no **macOS** (onde foi validado na
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
     **pergunta** → Pedir dica → Responder → 2ª resposta → **comparação**.
4. `python -m app.devtools.esp_probe` — se a placa estiver na USB, confirma o
   heartbeat do firmware e que o LCD redesenhou (`draw_ok`). Não grava firmware.

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

- O toque virtual fala com o bridge, não com a placa: para simular toques
  **dentro** do firmware seria preciso um comando de depuração no ESP e gravar
  um firmware novo (não feito).
- `tests/test_mac_serial.py` usa pseudo-terminal POSIX e é pulado no Windows.
- Testes que criam links simbólicos são pulados no Windows sem Modo de
  Desenvolvedor.
- O teste do firmware em C (`iot/nekomind_firmware/scripts/test_firmware.sh`)
  precisa de um compilador C (no Windows, instale MSYS2/MinGW `gcc`).
