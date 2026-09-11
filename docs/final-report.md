# Relatório final — NekoMind

## Publicação

Código **publicado e verificado no GitHub** em 11/09/2026 usando
`LeandroRochaDosPrazeres`, com permissão `push=true`, remote HTTPS e push normal.
Repositório: [maya-gc/NekoMind](https://github.com/maya-gc/NekoMind). Branch única:
[feat/nekomind-touch-mac-mvp](https://github.com/maya-gc/NekoMind/tree/feat/nekomind-touch-mac-mvp).

- SHA inicial: `7c987ac4b035cad163867810f9683964162f73b7`.
- SHA final do código desta rodada: `9032983246684a5a9c2120c070a17621cb741842`,
  confirmado por `git ls-remote`, novo fetch e API GitHub.
- `main` permaneceu em `0a4bdfb4278858bd7e10ec69f7825ba1ebdcdafd`.
- Commits iniciais `2ff3535`, `412146c` e `7c987ac` preservados; bundle local verificado.
- Este relatório e as capturas compõem um commit adicional de fechamento documental.
  O SHA desse fechamento é informado na resposta de entrega após sua verificação remota;
  o SHA acima identifica precisamente o código testado, sem incluir o próprio relatório.
- Nenhuma branch/fork novo, merge em main, reset, rebase, force-push, deploy ou modelo
  de nuvem foi usado.

**Incidente de dados:** uma revisão desta execução executou indevidamente
`drop_all/create_all` no banco local padrão. O conteúdo anterior não foi inventariado;
portanto, não é possível afirmar ausência de perda. Uma cópia foi preservada e a
recuperação SQLite encontrou somente registros sintéticos posteriores. Dados anteriores
não foram recuperados; eventual restauração depende de backup externo. O bundle Git
não contém o banco. Detalhes e medidas posteriores estão no [QA](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/qa-report.md).

Comandos de publicação/verificação executados:

```bash
gh auth switch --hostname github.com --user LeandroRochaDosPrazeres
gh api user --jq .login
gh api repos/maya-gc/NekoMind --jq .permissions
git fetch origin
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin HEAD:refs/heads/feat/nekomind-touch-mac-mvp
git ls-remote --heads origin feat/nekomind-touch-mac-mvp main
gh api repos/maya-gc/NekoMind/branches/feat/nekomind-touch-mac-mvp --jq .commit.sha
git rev-list --left-right --count HEAD...origin/feat/nekomind-touch-mac-mvp
```

## Commits

| SHA completo / URL | Mensagem | Objetivo | Principais arquivos |
|---|---|---|---|
| [9032983246684a5a9c2120c070a17621cb741842](https://github.com/maya-gc/NekoMind/commit/9032983246684a5a9c2120c070a17621cb741842) | fix(mvp): corrigir calibração, pausa e histórico | Corrigir janela e primeiro uso da calibração, persistência/exibição da data e instrução de pausa | `backend/app/mac/capture.py`; `backend/app/services/session_analysis.py`; `frontend/web/src`; testes |
| [fd5c0a2136ad33f55f6b6079f9154005344bf07b](https://github.com/maya-gc/NekoMind/commit/fd5c0a2136ad33f55f6b6079f9154005344bf07b) | feat(backend): integrar operação, recuperação e privacidade NM-008 a NM-019 | APIs, migração aditiva, captura/calibração, retomada, retenção, autenticação e testes | `backend/app; backend/tests` |
| [d52815dc51502c85ade662bd0e6b760b167a4e82](https://github.com/maya-gc/NekoMind/commit/d52815dc51502c85ade662bd0e6b760b167a4e82) | feat(firmware): renderizar avatar, jornada e cartões touch | Controlador C, parser, display-list e layouts independentes de drivers | `iot/nekomind_firmware` |
| [9e88e2472f5892aa45d263624a3fa7ef299bb280](https://github.com/maya-gc/NekoMind/commit/9e88e2472f5892aa45d263624a3fa7ef299bb280) | feat(web): integrar feira e painéis público e operacional | Emulador, painéis, cartões, fila com recibos e regressões | `frontend/web; frontend/tests; frontend/streamlit/services/backend_client.py` |
| [fa554202593b982f6e133b7dab791f388d4be542](https://github.com/maya-gc/NekoMind/commit/fa554202593b982f6e133b7dab791f388d4be542) | fix(web): distinguir recuperação desconhecida antes de autenticar | Evitar informar falsamente ausência de recuperação antes de consultar dados privados | `frontend/web/src/render.mjs`; teste web |

Os três commits anteriores permanecem ancestrais. A revisão documental não altera o
código desses commits. O relatório distingue publicação, execução automatizada e
validação física; o MVP físico não está declarado completo.

Em um reteste posterior no mesmo Mac, a jornada conectada percorreu diagnóstico,
início, pausa, retomada, finalização, cartões, nova tentativa, cancelamento confirmado,
assunto e histórico. O microfone físico capturou voz sintetizada localmente; a pausa
não gravou bytes e o WebRTC VAD detectou fala no WAV final. Foram corrigidos a janela
de calibração, o diretório ausente no primeiro uso, a data final da sessão, o campo de
data do histórico e a instrução exibida durante a pausa. As contagens atuais na seção
Testes substituem a baseline `178` indicada na matriz histórica abaixo.

## Melhorias NM-001 a NM-019

A matriz abaixo contém implementação, arquivos e evidências. As contagens se referem
às suítes e não são somáveis por melhoria. `Software testado` não significa hardware
validado. A matriz operacional também está em [delivery.md](delivery.md).

| NM | Status | Arquivos / implementação | Testes | Evidência | Pendências |
|---|---|---|---|---|---|
| 001 | Software testado; validação real pendente | Resultado correlacionado por sessão, origem, tipo e estado; `mac/protocol.py`, `mac/bridge.py`, `neko_controller.c` | `test_mac_bridge`, `test_touch_mac_end_to_end`, C | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Falhas, atraso e timeout automatizados; serial físico pendente |
| 002 | Software testado; validação real pendente | Cache lazy por configuração, lock de inicialização/gerador e cleanup; `adapters/asr_adapter.py`, `main.py` | `test_asr_lifecycle` | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | 10 casos unittest com modelo substituto; Whisper real e benchmark pendentes |
| 003 | Software testado; validação real pendente | Captura Mac e comandos touch confirmados; `mac/capture.py`, `mac/bridge.py`, `session_controller.c` | `test_mac_capture`, `test_mac_serial`, integração | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Microfone/serial substitutos; drivers físicos pendentes |
| 004 | Software testado; validação real pendente | Configuração explícita e origem de cada etapa; `config.py`, `session_analysis.py`, painéis | `test_modes`, `test_session_analysis_guards`, Streamlit | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Sem fallback silencioso; ASR real não executado |
| 005 | Software testado; validação real pendente | WAV, WebRTC VAD e qualidade/clipping; `audio_processing.py`, `audio_quality.py` | `test_speech_validation`, `test_calibration` | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Sinais sintéticos; limiares precisam de calibração na bancada |
| 006 | Software testado; validação real pendente | Recibos persistentes, CAS, IDs não reutilizados e fila pendente; `session_repository.py`, `operations.py`, `bridge.py`, `state.mjs` | `test_audio_idempotency_and_capture_state`, `test_privacy_failures`, `test_mac_bridge`, Node | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Concorrência/reenvio/exclusão cobertos; esperas limitadas |
| 007 | Local lexical implementado e testado | Extração lexical explícita ancorada na transcrição; `adapters/llm_adapter.py`, `topic_extraction.py` | `test_topic_extraction_real` | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Local/offline; limitações linguísticas, sem avaliação factual |
| 008 | Software testado; validação real pendente | Autoteste assíncrono por componente; `routes_experience.py`, `bridge.py`, `capture.py` | `test_mac_bridge`, `test_calibration`, `test_operations` | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Demo dispensa hardware real; disponibilidade física não atestada |
| 009 | Software testado; validação real pendente | Manifesto fsynced, chunks/cursores persistidos e retomada explícita; `capture.py`, `bridge.py`, `session_lifecycle.py` | `test_mac_capture`, `test_mac_bridge`, `test_session_lifecycle_nm019` | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Recuperação automatizada; mic não reabre sozinho |
| 010 | Software testado; validação real pendente | Retenção, exclusão confirmada, tombstone e scrub de recibos; `session_lifecycle.py`, `migrations.py` | `test_privacy_failures`, `test_session_lifecycle_nm019` | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Falha parcial recuperável; backups/SSD fora da garantia. Ver incidente no QA |
| 011 | Software testado; validação real pendente | Assunto confirmado/corrigível, histórico e versão de métrica; `routes_sessions.py`, `session_lifecycle.py`, painéis | `test_session_lifecycle_nm019`, Node | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Mesmo assunto/método; tendências não provam domínio |
| 012 | Software testado; validação real pendente | Calibração curta explícita, identidade do microfone e descarte da amostra; `capture.py`, `audio_quality.py` | `test_calibration`, `test_mac_capture` | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Sem gravação de pessoa; bancada real pendente |
| 013 | Implementado; QA visual/interativo parcial | Modo feira, reinício, geração e limpeza de projeção; `routes_experience.py`, `frontend/web` | `test_operations`, `test_experience_end_to_end`, Node | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | QA no navegador; fluxo físico pendente |
| 014 | Software testado; validação real pendente | Avatar original por estado, expressão e redução de movimento; `render.mjs`, `styles.css`, `neko_layout.c` | Node, C e screenshots | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Memória/FPS no ESP32 não medidos |
| 015 | Software testado; validação real pendente | Nível/clipping no Mac e telemetria limitada; `capture.py`, `bridge.py`, `neko_protocol.c` | `test_mac_capture`, `test_mac_serial`, C | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Nível não é detector de fala; latência física pendente |
| 016 | Software testado; validação real pendente | Jornada persistida com eventos/durações e origem; `journey.py`, `session_analysis.py`, bridge/painéis | `test_session_lifecycle_nm019`, integração, C | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Sem porcentagem fictícia; ASR real não medido |
| 017 | Implementado; QA visual/interativo parcial | `/public` somente leitura, sem transcrição integral/administração; `routes_experience.py`, `render.mjs` | `test_operations`, Node, QA navegador | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Uso local; televisão física não testada |
| 018 | Implementado; QA visual/interativo parcial | Cartões com conteúdo, origem e ações grandes; `state.mjs`, `neko_layout.c` | Node, C, QA 240×320 e 320×240 | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Fontes/legibilidade do módulo físico pendentes |
| 019 | Implementado; QA visual/interativo parcial | `/presenter` reservado por token local, diagnóstico e ações confirmadas; `security.py`, `routes_experience.py`, `frontend/web` | `test_operations`, Node, QA navegador | [QA por grupo](qa-report.md); suíte backend 178, web 25, Streamlit 6 e host C 22 casos | Token em memória; somente local |

Paths Python relativos a `backend/app`, testes a `backend/tests`, C a
`iot/nekomind_firmware/main`. Consulte os [arquivos publicados](https://github.com/maya-gc/NekoMind/tree/feat/nekomind-touch-mac-mvp) e o
[inventário de testes por arquivo](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/qa-report.md).

## Backend

FastAPI recebe comandos locais autenticados e mantém sessões em SQLite. O bridge Mac
captura áudio PCM16 mono/16 kHz em uma sessão explicitamente iniciada. Confirmação de
captura, pausa, retomada e término são ligadas ao recorder; USB não carrega áudio.
A finalização encerra captura, valida WAV/fala/qualidade, transcreve, extrai tópicos e
persiste resultado antes de liberá-lo aos consumidores.

WebRTC VAD, duração mínima de fala e indicadores de nível/clipping/ruído impedem
avaliação pedagógica sobre silêncio ou captação insuficiente. Pausas de raciocínio
não encerram automaticamente a sessão. Demo continua identificado e pode usar silêncio.
ASR usa cache por modelo/dispositivo/compute_type, lazy, locks e cleanup; autoteste
explícito pode antecipar a carga local, sem download automático. `local_keywords` é
extração lexical local efetiva, com termos ancorados na transcrição, sem mock oculto,
API externa ou promessa de correção factual.

Migrações aditivas inspecionam esquema existente e criam backup consistente SQLite
antes de alterar colunas. Transações/CAS, recibos duráveis e tombstones impedem
inícios/finalizações duplicados e reutilização de IDs apagados. A jornada registra
origem, estado e duração. Recuperação retoma análise já iniciada sem reabrir microfone;
retomada de captura requer ação explícita. Cancelamento invalida respostas tardias.
Retenção configurável e exclusão confirmada cobrem arquivos locais conhecidos,
transcrição, tópicos, métricas e recibos; falha parcial permite repetir limpeza.

Novas rotas incluem assunto/histórico, recover/cancel/delete e experiência
public/presenter/commands/bridge/providers. Token local 0600, APIs privadas com Bearer,
um worker, loopback e sem reload. Público recebe allowlist sem transcrição/token.
[API](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/api_contract.md), [dados e rollback](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/data_model.md),
[privacidade](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/privacy-retention.md). **178 testes backend aprovados.**

## Frontend

Modo normal e feira são separados. Feira oferece atração, prontidão, captura, jornada,
cartões e reset para o próximo visitante. `/touch` é emulador do display;
`/public` mostra rosto, estado, jornada e tópicos, somente leitura;
`/presenter` exige token em memória e reúne prontidão, sessão, assunto/histórico,
calibração, recuperação, cancelamento e reset. Streamlit mantém histórico/demo.
Nenhuma interface grava áudio pelo navegador.

Cartões usam uma informação por vez, paginação por texto, botões anterior/próximo,
retry e encerramento. Origem fica visível; rascunhos e navegação são reconciliados por
sessão. Fila distingue aceitação HTTP de ACK Mac e mantém request_id em retransmissão.
Confirmações destrutivas usam diálogo na página, Escape/foco e escolhas explícitas.
Avatar original SVG/C possui expressões, sinais textuais e redução de movimento.

**25 testes web e 6 Streamlit aprovados.** Acessibilidade de markup/contrato e imagens
foram verificadas; interação final e auditoria completa WCAG não estão aprovadas.
[Superfícies](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/panels.md), [direção visual](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/ui-design.md).

## Firmware e protocolo

JSON Lines v1 sobre serial, request_id/session_id, estados correlacionados e limites
de espera. O parser rejeita tipo/conteúdo incorreto, sessão errada e mensagens antigas.
Há estados pronto/verificando/ouvindo/pausado/processando/concluído/erro/recuperação;
comandos de sessão, diagnóstico, calibração, recuperação, cancelamento e reset.
Voz/jornada compactas usam a solicitação correlacionada; voz tem limite de 5 Hz e para
fora da captura. Um teste passa a serialização Python pelo controlador C compilado.

Layouts e display-list em 240×320 e 320×240 mantêm rosto, modos, cartões e alvos grandes.
Navegação é local, com debounce; confirmação física exige novo toque após soltar.
**22 casos C portáteis passaram**, com `-std=c11 -Wall -Wextra -Werror`.
Build ESP-IDF, flash e validação física **não executados**. O módulo anunciado é
Teknimas 2,4", SPI, ILI9341; placa, controlador touch, pinos, tensão, revisão e montagem
continuam sem identificação. Drivers `board_touch`/desenho de cena são fronteiras
pendentes e não integração física pronta. [Protocolo](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/iot_protocol.md),
[hardware](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/hardware-teknimas-ili9341.md).

## QA visual

Inspeção real no navegador local em 240×320, 320×240 e 1440×900. Layout1920×1080 teve
medidas DOM, mas a captura integral sofreu corte/artefato do navegador embutido.
Foram abertos estados de atração, diagnóstico/aprovado/erro, pronto, gravação,
voz baixa, clipping, pausa, transcrição, extração, preparação, resultado, recuperação,
reset, público e presenter. Fixtures REAL estão explicitamente marcadas QA/EMULADOR.

Corrigidos textos sobrepostos, aviso de voz baixa, botão Pausar cortado, resumo sobre
navegação e duplicação de resumo que ocultava tópicos no painel. O fluxo demo conectado
foi observado até resultado persistido e cartão de tópico, sempre na mesma sessão.
A confirmação nativa bloqueou o navegador; após substituí-la, a repetição interativa
final de reset/retry/histórico/exclusão permaneceu não concluída. Os testes de API e
contrato correspondentes passaram. **QA parcial, sem aprovação irrestrita.**

- [Resultado vertical](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/ScreenshotsToCloseLoop/runs/feira-nm019/touch-result-240x320.png)
- [Resultado horizontal](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/ScreenshotsToCloseLoop/runs/feira-nm019/touch-result-320x240.png)
- [Gravação demo conectada](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/ScreenshotsToCloseLoop/runs/feira-nm019/connected-recording-320x240.png)
- [Painel público](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/ScreenshotsToCloseLoop/runs/feira-nm019/public-result-1440x900.png)
- [Presenter](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/ScreenshotsToCloseLoop/runs/feira-nm019/presenter-recovery-1440x900.png)

As 33 capturas versionadas incluem baseline, fixtures e fluxo conectado; os problemas
de enquadramento foram preservados fora do Git. [QA completo](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/qa-report.md).

## Testes

| Grupo | Comando / método | Quantidade / aprovados | Falhas finais / não executados |
|---|---|---|---|
| Estática | Ruff check, Ruff format, compileall, node --check, bash -n, git diff --check | PASS; 68 arquivos Python formatados | Type checker não configurado; scanners externos indisponíveis |
| Backend | `cd backend; .venv/bin/python -m pytest -q` | 180/180 | 0; 6 avisos de depreciação |
| ASR/lifespan | `cd backend; .venv/bin/python -m unittest discover -s tests -p test_asr_lifecycle.py -v` | 10/10 | 0; modelo substituto |
| Frontend web | `node --test frontend/tests/*.test.mjs` | 25/25 | 0 |
| Streamlit | `python3 -m pytest frontend/streamlit/tests -q` | 6/6 | 0; Python global com dependências |
| Firmware | `bash iot/nekomind_firmware/scripts/test_firmware.sh` | 22 casos, binário aprovado | Build ESP-IDF não executado |
| Integração | pytest touch_mac_end_to_end + experience_end_to_end + serial_interop | 6/6, grupo separado | Sem mic/ASR físicos |
| Privacidade/migração | pytest privacy_failures + session_lifecycle_nm019 + sqlite_migration | 21/21, grupo separado | Backups externos fora da garantia |
| Painel operacional | pytest test_operations.py | 20/20, grupo separado | Jornada interativa final também executada em loopback |
| Visual | Navegador e capturas abertas | 33 imagens selecionadas e reteste interativo | Tela física e captura integral 1920×1080 pendentes |
| Desempenho | Limite de telemetria e concorrência com substitutos | Casos automatizados aprovados | Sem benchmark Whisper/RSS/FPS/latência física |
| Hardware real | Microfone/PortAudio Mac | Executado com voz sintetizada local | Whisper, serial, ESP32 e TFT/touch não executados; nenhuma pessoa gravada |

Contagens sobrepostas não se somam. O gate agregado do runtime Flow permaneceu FAIL
pela política herdada de `.env.example`; doctor teve pendência de steering global.
Esses resultados não foram ocultados nem confundidos com testes funcionais aprovados.
Comandos completos, avisos e inventário por arquivo estão no [QA](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/qa-report.md).

## Como executar

```bash
PYTHON_BIN=python3.12 bash scripts/setup_backend.sh
backend/.venv/bin/python -m pip install -r backend/requirements-mac.txt
cp -n backend/.env.example backend/.env
bash scripts/run_backend.sh
# Outro terminal, a partir da raiz:
cd backend
.venv/bin/python -m app.mac --simulate
```

Padrão demo: sem microfone/modelo físico. Abrir `http://127.0.0.1:8000/touch`,
`/public` ou `/presenter`; informar token local apenas no controle reservado e
escolher Feira ou Normal no presenter. Para o dispositivo físico, trocar `--simulate`
por `--port /dev/cu.PORTA_CONFIRMADA`, após identificar a placa e drivers.
Permitir microfone ao terminal no macOS somente para ensaio autorizado; manter Mac
ligado, tampa aberta e sem suspensão.

Modo real local: instalar `backend/requirements-real.txt`, preparar modelo CTranslate2
local e configurar `NEKOMIND_MODE=real`, `NEKOMIND_ASR_PROVIDER=faster_whisper`,
`NEKOMIND_ASR_MODEL_SIZE=/caminho/do/modelo`, `NEKOMIND_LLM_PROVIDER=local_keywords`.
Reiniciar backend/bridge após configuração. Sem chave/API/cloud. Não há download
silencioso. Instalar requirements-test para pytest; Node executa os testes web sem
build. Instalar dependências Streamlit no interpretador usado para seus testes.
[Instalação](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/README.md), [roteiro real de mesa](https://github.com/maya-gc/NekoMind/blob/feat/nekomind-touch-mac-mvp/docs/manual-checklist.md).

## Pendências reais

- **Decisão necessária:** identificar placa ESP32, controlador touch, pinos, tensão,
  revisão e orientação da unidade comprada. `local_keywords` já está aceito como opção;
  trocar para outro modelo/API seria decisão futura.
- **Hardware indisponível/sem identificação:** drivers, build ESP-IDF, flash, TFT e touch
  reais. Nenhum teste portátil comprova funcionamento do módulo.
- **Testes não executados:** gravação de uma pessoa, Whisper real, benchmark,
  latência serial/FPS/RAM no ESP32 e ensaio completo da mesa com o dispositivo físico.
- **Limitações conhecidas:** extração lexical e métricas não verificam fatos/domínio;
  VAD/níveis precisam de calibração real; SQLite/loopback/um worker; apagamento não
  alcança backups externos ou recuperação forense do SSD. Gate global Flow não aprovado.
- **Incidente de dados:** banco padrão foi recriado indevidamente durante revisão;
  dados anteriores não recuperados. A cópia pós-incidente permanece preservada e
  recuperação adicional depende de backup externo.
- **Melhoria futura:** outros extratores, microfone embarcado e autonomia sem Mac
  permanecem fora desta entrega.
