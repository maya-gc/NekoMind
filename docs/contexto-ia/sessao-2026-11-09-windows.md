# Sessão 09/11/2026 — Windows + macOS e pipelines de teste

Ferramenta: Claude (sessão com acesso ao Windows da Maya pela ponte do app
desktop). Branch de trabalho: `feat/multiplataforma-pipelines`, depois unida
em `main`.

## Pedido

Adaptar o projeto para Windows **sem remover o que funciona no Mac**, criar uma
pipeline automática (sem alto-falante, sem tocar no display, usando o áudio do
próprio computador) separada da pipeline manual de bancada, e atualizar o
contexto e o repositório.

## Diagnóstico inicial no Windows (antes das mudanças)

- Placa ESP32-S3 em `COM3` (VID 0x303A): heartbeat `status` a cada ~2,6 s e
  `display_ack` com `draw_ok=true` — firmware e LCD funcionando.
- Frontend: 40/40 testes.
- Backend não subia: `os.O_NOFOLLOW` e a checagem de permissão `0600` do token
  não existem no Windows (79 testes caíam nisso). O bridge importava `fcntl`.

## Decisões

| Tema | Decisão |
|---|---|
| Portabilidade | Adaptadores em `backend/app/platform_support.py`. No macOS cada função faz exatamente o que o código fazia antes (`O_NOFOLLOW`, `0600`, `fcntl.flock`, `caffeinate`, `afplay`). No Windows: recusa explícita de link, ACL do perfil do usuário, `msvcrt.locking`, `SetThreadExecutionState`, `Media.SoundPlayer`. |
| Testes POSIX | Nenhum teste apagado. `pty` e criação de link simbólico são pulados no Windows; a checagem `0600` continua valendo no Mac. |
| Microfone na pipeline | `FileRecorder` reproduz WAVs como se fossem o microfone. As respostas são faladas pela voz do sistema (SAPI “Microsoft Maria” no Windows, `say` no Mac) direto para arquivo. |
| Voz da gatinha | `--voice silent` (registra o texto em `falas.jsonl`) e `--voice kokoro-file` (gera WAV sem tocar). |
| Toque | `VirtualTouch` envia as mesmas linhas JSON do firmware pelo codec real. Simular toques dentro do ESP exigiria firmware novo — não feito. |
| ASR na pipeline | `roteiro` por padrão (texto conhecido, sem modelo); `--asr whisper` usa faster-whisper. VAD WebRTC é real. |
| Bug encontrado | Conexão SQLite do diário do bridge usada por várias threads sem trava → `OperationalError: not an error` intermitente. Corrigido com proxy serializado (API inalterada). Afeta também o Mac. |

## Evidência (Windows 11, Python 3.13.15, placa em COM3)

Execução `scripts\test_auto.ps1` no commit `9b1eebb`:

| Etapa | Resultado |
|---|---|
| Backend (pytest) | 215 passaram, 5 pulados (pty, links simbólicos, compilador C) |
| Frontend (node --test) | 40/40 |
| Pipeline toque virtual | APROVADO — demo (7 etapas) e guiado: material → diagnóstico → missão → 1ª resposta → pergunta → dica → 2ª resposta → comparação “Agora: esfria e forma as nuvens. Antes, esse trecho não apareceu.” |
| Placa ESP (USB) | PLACA OK — 6 comandos, 5 `display_ack`, 0 falhas de desenho |

## Não verificado nesta sessão

- **macOS:** não havia Mac disponível. O caminho do Mac foi preservado por
  construção (mesmas chamadas) e precisa de uma rodada de
  `bash scripts/test_auto.sh` + bancada para confirmar.
- Toque físico (XPT2046), voz Kokoro no Windows e ASR real com a voz da
  usuária não foram exercitados.

---

# Segunda rodada (09/11/2026, tarde) — deixar o projeto “redondo”

Pedido: executar as sugestões aprovadas — fechar lacunas de verificação,
robustecer a pipeline e preparar a apresentação. Apresentação e vídeos serão
no **Mac**; desenvolvimento e mídias no **Windows**.

## O que foi feito

| Tema | Entrega |
|---|---|
| CI | `.github/workflows/testes.yml`: Windows e macOS a cada push — pytest, frontend, firmware em C, pipeline, checklist em plano B e, no Mac, `scripts/test_auto.sh`. Primeira prova de que o caminho do Mac funciona: no runner macOS passaram os testes exclusivos de POSIX (pty, permissão 0600). |
| Firmware em C no Windows | `app.devtools.c_compiler` usa `cc/gcc/clang` ou o clang do `ziglang` (pip). `test_serial_interop` deixou de ser pulado no Windows. |
| Pipeline | 7 cenários (demo, guiado, longo, errada, silêncio, ruído, queda do USB), orçamento de tempo, `--repeticoes`, `--capturas` (Edge/Chrome via Playwright) e relatório HTML. |
| Toque no firmware | Comando de depuração `!tap <botão>` / `!tap x y`: o firmware executa o toque pelo mesmo hit test do dedo. `app.devtools.esp_tap_flow` roda o fluxo guiado inteiro na placa esperando cada `display_ack`. Firmware compilado e **gravado** na placa da Maya (COM3), hash verificado. |
| ASR real | `scripts/baixar_modelo_asr` + `--asr whisper`. Encontrado e corrigido bug: PyAV atual não aceita um argumento que o faster-whisper 1.2.1 passa → toda transcrição real falhava (`analysis_failed`). O adaptador agora lê o WAV PCM16 16 kHz do bridge diretamente. Isso também quebraria o Mac numa instalação nova. |
| Apresentação | `app.devtools.preflight` + `scripts/apresentar.sh/.ps1` (checklist, backend, bridge, telas) e plano B em demo identificado; `docs/apresentacao.md` (véspera, roteiro de 3 min, vídeo no Mac, perguntas da banca); README vitrine. |

## Evidência no Windows da Maya (placa em COM3)

- `test_auto.ps1`: pytest 216 ok, frontend 40/40, pipeline 7/7 cenários
  aprovados, firmware em C ok (ziglang), placa ok.
- `esp_tap_flow` com o firmware novo: Diagnóstico → Pronto → Começar →
  Gravando → Finalizar → pergunta → dica → Responder → comparação → Voltar,
  todos confirmados pelo LCD (`display_ack`) — **PLACA APROVADA**.
- CI verde em Windows e macOS (commit `309b738`).
- Pipeline com **ASR real** (`--asr whisper`, modelo `small` em CPU): 7/7
  cenários aprovados; ~4,3 s por resposta analisada (transcrição ~1,8 s);
  14 capturas de tela sincronizadas com o estado.
- Checklist pré-palco no Windows: **PRONTO PARA APRESENTAR** (placa, microfone
  fifine, faster-whisper em cache, VAD); avisos só para voz silenciosa e Ollama.

## Observações para mídias

- Na tela pública do guiado aparece “0% dos pontos mencionados” mesmo com a
  comparação dizendo que o trecho apareceu: o material curto vira 1 ponto
  longo e a cobertura é lexical. Revisar a regra antes de filmar.
- Capturas feitas com `--asr roteiro` mostram “faster_whisper/REAL” nas telas
  porque o roteiro substitui só a transcrição. Para mídia pública, gere com
  `--asr whisper` (transcrição de verdade).
- A captura por arquivo aparece na jornada como `mac_microphone`; é a voz do
  sistema, não uma pessoa. Não usar essas telas como prova de uso real.
