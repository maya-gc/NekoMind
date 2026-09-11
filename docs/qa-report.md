# QA — NekoMind NM-001 a NM-019

Data: 11/09/2026. Branch: `feat/nekomind-touch-mac-mvp`. Base preservada:
`7c987ac4b035cad163867810f9683964162f73b7`.

## Ambiente e isolamento

macOS arm64, Python 3.12.13 na venv backend, FastAPI 0.141.1, SQLAlchemy 2.0.52,
pytest 9.1.1, WebRTC VAD wheels 2.0.14, sounddevice 0.5.3 e pyserial 3.5.
Frontend web testado com Node 25.8.0; Streamlit com o Python global que contém suas
dependências. Firmware host compilado com `cc -std=c11 -Wall -Wextra -Werror`.

Pytest configura banco temporário antes de importar o app e diretórios de áudio/Mac
por teste. O teste unittest de lifespan usa engine/settings temporários explícitos.
QA no navegador usa backend em loopback, banco e storage temporários, modo demo e
recorder sintético. O reteste físico desta rodada usou PortAudio, o microfone e os
alto-falantes reais do Mac com voz sintetizada por `/usr/bin/say`. Nenhuma gravação de
pessoa, download de modelo ou serviço de inferência em nuvem foi usado.

## Incidente durante a execução

Uma revisão automatizada fora do procedimento de teste executou `drop_all/create_all`
contra o banco local padrão, recriando suas tabelas. Foi uma ação indevida da execução,
não uma migração do produto. O conteúdo anterior não foi inventariado e **não é
possível afirmar ausência de perda de dados**.

O incidente foi informado ao usuário. Uma cópia do banco após o incidente foi
preservada fora do Git. Não foram encontrados backups locais ou snapshots APFS;
a tentativa SQLite `.recover`, executada somente numa cópia, encontrou apenas os
registros sintéticos posteriores. Os dados anteriores não foram recuperados.
Uma eventual recuperação depende de backup externo. O bundle Git foi preservado e
verificado; ele não é backup do banco.

Depois do incidente, todas as verificações de banco ficaram restritas às fixtures
temporárias. Também foi corrigido o teste legado do lifespan, que inicializava o
storage padrão, e separado o diretório de arquivos de cada teste.

## Auditoria e falhas corrigidas

- A baseline NM-001..007 passou nos grupos existentes, mas não cobria clipping.
  Foram adicionados qualidade PCM, clipping e testes sintéticos.
- Exclusão parcial bloqueava toda tentativa seguinte; o tombstone agora permite
  repetir a limpeza e impede nova análise.
- Um link simbólico de diretório podia autorizar caminho externo. O caso foi
  reproduzido em diretório temporário e passou a ser rejeitado.
- Respostas no journal Mac conservavam tópicos após exclusão; agora ficam somente
  recibos sem conteúdo. Recibos pendentes são preservados até ACK.
- Falha de limpeza após resultado persistido causava erro de análise; agora mantém
  o resultado e permite repetir apenas a limpeza.
- IDs de sessão eram reutilizados após exclusão; tombstones e alocação sob transação
  impedem reutilização e colisão entre inícios concorrentes.
- Cancelamento durante ASR podia ser sobrescrito pelo worker; regressão concorrente
  cobre a confirmação antes da conclusão do worker.
- GET público disparava reset por inatividade, e ACK antigo podia limpar a sessão
  seguinte; o reset passou ao bridge autenticado e é validado por sessão/geração.
- Contratos de manifesto, fila HTTP e telemetria foram cruzados entre produtores e
  consumidores, além dos testes unitários.
- QA visual encontrou overflow do diagnóstico, aviso de voz baixa, botão Pausar
  cortado no landscape e resumo duplicado que escondia tópicos na TV.
- O uso interativo encontrou instrução genérica durante a pausa; o touch agora informa
  que a captura está pausada e orienta a ação Retomar.
- Sessões concluídas perdiam `ended_at` porque um `refresh` ocorria depois da atribuição,
  e o histórico web ignorava o nome de campo do contrato. A ordem foi corrigida e o
  renderer passou a consumir `ended_at`.
- A calibração de três segundos aguardava somente 100 ms e falhava no primeiro uso se
  `capture/` ainda não existisse. Agora respeita a janela solicitada e cria o diretório.

## Evidência visual

Capturas em `ScreenshotsToCloseLoop/runs/feira-nm019/`. Arquivos com `fixture` na tela
são estados determinísticos para QA e **não evidência de microfone/modelo reais**.
O primeiro `initial-before-240x320.png` registra o problema antes da correção.

Viewports: 240×320, 320×240, notebook 1440×900 e layout TV 1920×1080.
No viewport TV maior, a captura do navegador embutido apresentou corte/artefato;
o enquadramento integral foi conferido em 1440×900, com medidas DOM do layout maior.
Isso não é validação de televisão física.

O fluxo conectado no navegador atravessou autoteste → pronta → gravando S1 → pausa
S1 → retomada S1 → resultado demo persistido S1 → cartão de tópico. Foi usado
DemoRecorder, SQLite e API reais locais, sem microfone/modelo reais. Capturas
`connected-*` registram esse ensaio anterior ao último ajuste de confirmação.

A confirmação nativa de encerramento que bloqueava a automação foi substituída por
diálogo acessível dentro da página, com confirmação/cancelamento e teste unitário.
Na repetição interativa final, o navegador percorreu diagnóstico, início, pausa,
retomada, finalização, cartões, nova tentativa deliberada, cancelamento confirmado,
assunto e histórico. Uma nova sessão após a correção confirmou `ended_at` tanto no
detalhe persistido quanto no ponto retornado pelo histórico. O ensaio foi em modo demo;
não há aprovação irrestrita de QA visual ou acessibilidade.

Na última inspeção de imagens, o resumo em 320×240 ainda invadia os botões.
A paginação foi reduzida a 32 caracteres por trecho, respeitando palavras; novas
capturas 240×320 e 320×240 foram abertas e mostraram texto separado da navegação.
As etapas de extração e preparação do resultado também foram capturadas e abertas
nas duas orientações. Atributos `REAL + QA + EMULADOR` dessas fixtures descrevem
apenas a apresentação de um estado real simulado, não processamento real.

Capturas com problemas de enquadramento em 1920×1080 foram preservadas localmente
como artefatos de diagnóstico fora do Git; não são apresentadas como evidência aprovada.

## Resultados finais por grupo

Comandos executados na raiz, salvo `cd backend` explícito. As linhas de integração,
privacidade e ASR são subconjuntos/execuções adicionais e não devem ser somadas ao total.

| Grupo | Comando / método | Quantidade e aprovados | Falhas finais / não executado |
|---|---|---|---|
| Estática | `backend/.venv/bin/ruff check backend/app backend/tests frontend/streamlit` | PASS | 0; erros de import/catch corrigidos |
| Formatação | `cd backend; .venv/bin/ruff format --check app tests` | 68 arquivos conformes | 0 |
| Sintaxe Python | `cd backend; .venv/bin/python -m compileall -q app tests` | PASS | 0 |
| Sintaxe JS/shell | `node --check frontend/web/src/*.mjs` individual; `bash -n` por script de produto | PASS | 0; não há type checker configurado |
| Backend completo | `cd backend; .venv/bin/python -m pytest -q --tb=short` | **180 / 180**, 16,75s | 0; 6 avisos de depreciação Starlette/httpx/AnyIO |
| ASR isolado | `cd backend; .venv/bin/python -m unittest discover -s tests -p test_asr_lifecycle.py -v` | **10 / 10** | 0; modelo substituto, lifespan real isolado |
| Frontend web | `node --test frontend/tests/*.test.mjs` | **25 / 25** | 0; estados, fila, contratos, cartões e a11y de markup |
| Streamlit legado | `python3 -m pytest frontend/streamlit/tests -q` | **6 / 6** | 0; usa Python global, venv backend sem Streamlit |
| Firmware portátil | `bash iot/nekomind_firmware/scripts/test_firmware.sh` | **22 casos**, binário C aprovado | 0; compilação host não é build ESP-IDF |
| Integração | pytest `test_touch_mac_end_to_end.py`, `test_experience_end_to_end.py`, `test_serial_interop.py` | **6 / 6**, execução separada | ASR/microfone substituídos; extrator lexical e C reais |
| Privacidade/persistência | pytest `test_privacy_failures.py`, `test_session_lifecycle_nm019.py`, `test_sqlite_migration.py` | **21 / 21**, execução separada | 0; isolamento, tombstones, backup e falhas parciais |
| Operação/painel | pytest `test_operations.py` | **20 / 20** | 0; snapshot público, auth, comandos, reset e ACK antigo |
| Visual | Navegador local + capturas abertas; 240×320, 320×240, 1440×900 | Estados listados e jornada interativa final concluída | Captura integral 1920×1080 parcial; sem tela física |
| Segredos/arquivos | Inventário Git + padrões de chaves privadas/GitHub/AWS, saída só de caminhos | 182 textos examinados antes do fechamento, 0 achados | Gitleaks/Semgrep/Trivy indisponíveis; não equivale a auditoria completa |
| Desempenho | Casos de limitação de voz/concorrência, tempos de etapas | Automatizado com substitutos | Sem benchmark de ASR, memória, FPS ou latência física |
| Hardware real | PortAudio/microfone Mac | **Executado** com voz sintetizada local; calibração e iniciar/pausar/retomar/finalizar | Whisper, serial, ESP-IDF/flash e TFT/touch não executados |

O gate agregado `.codex/scripts/codex-flow-quality-gates.sh .` permaneceu FAIL pela
regra que rejeita `.env.example` versionados, embora sejam exemplos sem credenciais
e exigidos nesta entrega; diff coverage também indisponível. O doctor inicial teve
72 PASS/18 WARN/5 FAIL; artefatos ausentes foram criados, mas steering global herdado
não foi alterado nem considerado aprovado. Esses gates de runtime são reportados
separadamente dos testes do produto. Não foi declarado TDD integral nem cadeia global
aprovada.

A revisão final das imagens também encontrou “Sem recuperação pendente” antes da
autenticação no presenter. O texto passou a indicar que a consulta exige token; a
regressão foi observada falhando, corrigida e a captura foi reaberta. A suíte web
final ficou em 25 testes aprovados.

## Inventário da suíte backend

| Arquivo em `backend/tests` | Aprovados |
|---|---|

| `test_asr_lifecycle.py` | 10 |
| `test_audio_idempotency_and_capture_state.py` | 11 |
| `test_calibration.py` | 5 |
| `test_experience_end_to_end.py` | 2 |
| `test_health.py` | 1 |
| `test_legacy_transport.py` | 2 |
| `test_mac_bridge.py` | 33 |
| `test_mac_capture.py` | 12 |
| `test_mac_serial.py` | 17 |
| `test_modes.py` | 8 |
| `test_operations.py` | 20 |
| `test_privacy_failures.py` | 7 |
| `test_serial_interop.py` | 1 |
| `test_session_analysis_guards.py` | 7 |
| `test_session_lifecycle_nm019.py` | 6 |
| `test_sessions.py` | 3 |
| `test_speech_validation.py` | 11 |
| `test_sqlite_migration.py` | 8 |
| `test_topic_extraction_real.py` | 10 |
| `test_touch_mac_end_to_end.py` | 3 |
| `test_transcription.py` | 3 |

## Capturas selecionadas e inspecionadas

- [Atração 240×320](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-attraction-240x320.png)
- [Gravação demo conectada](../ScreenshotsToCloseLoop/runs/feira-nm019/connected-recording-320x240.png)
- [Pausa demo conectada](../ScreenshotsToCloseLoop/runs/feira-nm019/connected-paused-320x240.png)
- [Voz baixa](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-low-voice-240x320.png) · [Clipping](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-clipping-240x320.png)
- [Erro de autoteste](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-checking-error-240x320.png) · [Recuperação](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-recovery-240x320.png)
- [Extração 240×320](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-processing-topics-240x320.png) · [Preparação 320×240](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-processing-result-320x240.png)
- [Resultado 240×320](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-result-240x320.png) · [Resultado 320×240](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-result-320x240.png)
- [Painel público 1440×900](../ScreenshotsToCloseLoop/runs/feira-nm019/public-result-1440x900.png)
- [Presenter 1440×900](../ScreenshotsToCloseLoop/runs/feira-nm019/presenter-recovery-1440x900.png)
- [Reset fixture](../ScreenshotsToCloseLoop/runs/feira-nm019/touch-reset-240x320.png), distinto do reset conectado testado pela API.

## Validação física e pendências

Faster-whisper real não está instalado/carregado; sem benchmark de primeira transcrição,
reuso ou memória. O microfone/PortAudio real capturou voz sintetizada pelos alto-falantes:
a calibração ficou pronta em cerca de 3,1 s, a pausa não acrescentou bytes e o WAV final
teve fala detectada por WebRTC VAD. Isso não valida transcrição Whisper nem captação de
uma pessoa na bancada. Um segundo ensaio isolado consumiu a mesma fila HTTP do touch no
`MacBridge`, abriu `MacRecorder` no microfone físico e concluiu uma sessão com
`capture_source=mac_microphone`: calibração `ready/ok` em 3,091 s, crescimento zero na
pausa, 172800 bytes após retomar, resultado demo persistido e áudio bruto removido.
Nesse ensaio, serial foi um substituto lógico e ASR/tópicos eram mocks identificados.
ESP-IDF build/flash não foi executado: placa, controlador touch, pinos e tensão não estão
definidos. Sem medição de FPS, RAM, PSRAM, latência serial física ou consumo do display.

Os comandos do roteiro físico estão em [manual-checklist.md](manual-checklist.md).
O software não deve ser apresentado como MVP físico totalmente pronto.
