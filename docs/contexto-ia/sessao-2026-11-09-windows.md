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

---

# Teste físico (10/11/2026, noite) — tutor IA real na placa

Windows da Maya, placa em COM3, `qwen2.5:7b` no Ollama, faster-whisper `small`,
commit `8e18fdc` na `consolidado`.

- Checklist: **PRONTO PARA APRESENTAR** — placa, microfone fifine,
  transcrição, VAD, **voz Kokoro carregada** e **tutor IA local** OK.
- Placa: 6 heartbeats, 6 telas desenhadas sem erro.
- Fluxo com toques dentro do firmware + ASR real + tutor IA: **PLACA
  APROVADA**; material curto virou 3 missões (uma por frase).
- Cenário Hamiltoniana (nível faculdade): pergunta da IA “Por que a
  Hamiltoniana é fundamental na equação de Schrödinger?”; dicas graduais
  diferentes (pista → analogia do “motor”); comparação específica
  (“Melhorou ao incluir autovalores, mas ainda falta…”). Ciclo da água com
  pergunta adaptada (“Por que a água do mar não forma nuvens diretamente?”).

Ajustes depois do teste: limites de tamanho explícitos no pedido à IA (2ª dica
e comparação eram cortadas no LCD), comparação deve ser específica e a
avaliação deve considerar o ponto da missão (a 1ª fala sobre “energia total”
foi julgada “correta” para o ponto “evolução temporal”: o modelo 7b ainda erra
esse julgamento às vezes).

---

# Terceira rodada (10/11/2026, 23h) — qualidade da IA, telas, Mac, manutenção

- **Avaliação do tutor** (`app.devtools.tutor_eval`, 24 falas): `qwen2.5:7b`
  foi de 10/24 para 13/24 exatos (22/24 tolerantes) com rubrica + exemplos +
  conferência dupla; ~2 s por julgamento. Ver `docs/tutor-ia.md`.
- **Telas:** `/public` mostra a avaliação da IA (sem ser nota); `/presenter`
  mostra “Revisar hoje”.
- **Mac:** `scripts/preparar_mac.sh` (Homebrew, Python 3.12, eSpeak, Kokoro,
  Ollama, modelos, checklist). Ainda não executado num Mac.
- **Manutenção:** `backend/constraints.txt` com as versões verificadas; PR #1
  fechado; branches antigas apagadas pelo Git da Maya (restam `main` e
  `consolidado`). Proteção da `main` precisa ser ligada pela Maya no GitHub
  (Settings → Branches), pois o acesso daqui não permite.

---

# Quarta rodada (13/11/2026) — robustez (prioridades alta e média)

| Item | Entrega |
|---|---|
| Avatar 3D x toque/serial | `session_task` mede cada quadro; acima de 30 ms passa a 250 ms, acima de 60 ms a 500 ms. Linha `saude:` a cada 30 s (pilha livre, pior quadro, intervalo). |
| Watchdog | Tarefa de sessão registrada no *task watchdog* (5 s, pânico → reinício). |
| Supervisor | `app.devtools.supervisor`: Ollama, backend e bridge com reinício e *backoff*, verificação de saúde, logs com rotação, backup do SQLite. Usado por `apresentar.ps1/.sh`. |
| Checklist | Item “Energia / suspensão” (aviso na bateria). |
| Resistência | `esp_tap_flow --minutos 60` + checagem de saúde do firmware. |
| Voz real | `app.devtools.gravar_voz` + cenário `voz_real` (pula com aviso se não houver gravações). |
| Código | `bridge.py` dividido: `journal.py` (diário SQLite), `study_memory.py` (memória e revisão), `tutor_flow.py` (pergunta, dicas, comparação, tutor IA). `except Exception` que engolem erro agora registram onde e o tipo (`app/errors.py`, nunca a mensagem, que pode conter transcrição). |
| CI | Testes C do firmware descobertos automaticamente; novo job compila o firmware com ESP-IDF v5.3. |

Pendente na máquina da Maya: gravar o firmware novo, rodar a resistência de
60 min e comparar `qwen2.5:14b` com `tutor_eval --modelo qwen2.5:14b`.

## Resultados na máquina da Maya (13/11/2026, tarde)

- **Voz real** (`voz_real`, faster-whisper): APROVADO; a transcrição da voz
  dela saiu exata (“A água do mar evapora com o calor do Sol.”).
- **`qwen2.5:14b`** no `tutor_eval`: 16/24 exatos (7b: 13/24), 24/24
  tolerantes, 3,1 s por julgamento (7b: ~2 s). Erro restante: tende a
  “parcial” onde o esperado é “correto” ou “não mencionou”.
- **Resistência** reprovou na 1ª rodada: na 2ª gravação o computador recebeu
  `Write timeout` e o laço serial morreu. Causa: o firmware lia só uma linha
  (no máximo 256 bytes) por volta de 50 ms + desenho, e o buffer USB enchia.
  Correção: o firmware esvazia até 16 linhas por volta e lê a linha inteira de
  uma vez; o computador tenta de novo e descarta o quadro em vez de derrubar o
  laço (no bridge real isso abortava a gravação e reconectava); o teste para
  na hora se o laço cair.

## Placa depois das correções (13/11/2026, tarde)

- Firmware com avatar em fatias + driver USB (commit `cb60a7c`): 10 min com
  21 fluxos completos e **1 hora com 125 fluxos completos, nenhuma tela de
  erro**, pilha livre estável (~8,8 KB), toques respondendo em 0,3–0,5 s
  (antes ~3 s). As reprovações restantes eram do próprio teste (passo
  “Placa conectada” esperava uma tela nova) e da fatia de 16 linhas (74 ms);
  corrigidas em `f88b5a2` (fatias de 8 linhas).
- Novo padrão do `scripts/resistencia.ps1`: teste rápido (~3 min) com 8
  fluxos + rajada de 300 quadros no USB; `-Minutos 60` para a véspera.
