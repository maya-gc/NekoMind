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
