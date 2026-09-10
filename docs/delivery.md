# Entrega NM-001 a NM-007 — 10/09/2026

Destino: `feat/nekomind-touch-mac-mvp`. A base remota foi lida/fetch antes das edições
e reconferida antes dos commits; não houve reset, alteração de main, merge ou force-push.
O pacote NM-002 parcial não estava disponível neste workspace: os requisitos foram
implementados no código atual e testados novamente, sem alegar aplicação do ZIP.

**Estado: implementação de software com testes automatizados; MVP físico ainda incompleto.**
Touch/display/RX serial precisam de drivers após escolha da placa. Microfone real,
Whisper real, calibração e adoção do extrator candidato não foram aprovados por testes
sintéticos. O firmware falha explicitamente enquanto touch físico estiver indisponível.

## Mapa de entrega

| Item | Arquivos principais | Testes executados | Pendência |
|---|---|---|---|
| NM-001 | `iot/.../main/neko_protocol.*`, `neko_controller.*`; `backend/app/mac/protocol.py`, `bridge.py` | Host C: resultado válido/antigo/inválido/outra sessão/sem resposta/timeout; `test_mac_bridge.py`, `test_touch_mac_end_to_end.py` | Validação física de estados/display |
| NM-002 | `backend/app/adapters/asr_adapter.py`, `main.py` | `test_asr_lifecycle.py`:10 testes, modelo substituto; lifespan FastAPI real | Modelo real, latência e memória não medidos |
| NM-003 | `backend/app/mac/{capture,backend,serial_loop,__main__}.py`; `iot/.../main/{board_touch,session_controller,display_ui}.*` | `test_mac_capture.py`, `test_mac_serial.py`, integração touch→API; host C | Escolher hardware e implementar touch/display/RX; microfone/permissão/mesa |
| NM-004 | `config.py`, adaptadores, `transcription.py`, `topic_extraction.py`, `session_analysis.py`, modelos/schemas, `frontend/streamlit/` | `test_modes.py`, guards, origens;6 testes frontend, AppTest e browser demo/real configurado | Execução real local integral ainda não feita |
| NM-005 | `audio_processing.py`, `session_analysis.py`; `requirements-real.txt` | `test_speech_validation.py`: WebRTC instalado com silêncio/ruído sintéticos; fala/níveis/pausas com detector substituto; integração rejeita silêncio | Calibrar falsos positivos/negativos e níveis com mic real |
| NM-006 | `bridge.py`, repositories, routes, `audio_ingestion.py`, `database/connection.py`; controlador C | toque/reenvio/perda ACK, concorrência start/finish/upload/capture-state, rollback/refresh, migração WAL e backup falho | Interrupção física USB/energia e testes prolongados |
| NM-007 | `adapters/llm_adapter.py`, `services/topic_extraction.py`, `session_analysis.py` | `test_topic_extraction_real.py`: assuntos diferentes, frases literais, resposta inválida/NaN/boolean/falha; integração associação correta | `local_keywords` funcional opt-in; decisão de adoção/modelo/provedor permanece aberta |

`iot/...` nesta tabela significa `iot/nekomind_firmware`. Todos os caminhos backend
sem prefixo completo pertencem a `backend/app`. O mapa inclui código e validação de
falhas, não apenas interfaces ou mocks. Nenhum dado real foi enviado à nuvem.

## Execução e resultados

- `backend/.venv/bin/python -m pytest backend/tests -q` → **106 passed**,5 avisos de
  depreciação Starlette/httpx/AnyIO/TestClient. Sem falha de teste ocultada.
- Dentro de backend: `.venv/bin/python -m unittest discover -s tests -p test_asr_lifecycle.py -v`
  → **10 testes OK**, incluídos nos106; não somar novamente.
- `python3 -m pytest frontend/streamlit/tests -q` → **6 passed**.
- `bash iot/nekomind_firmware/scripts/test_firmware.sh` → **firmware controller tests passed**,
  compilação host C11 com `-Wall -Wextra -Werror`, sem ESP-IDF.
- `backend/.venv/bin/python -m ruff check backend/app backend/tests frontend/streamlit`
  → **All checks passed**. Descritores FastAPI permitidos especificamente em B008.
- `backend/.venv/bin/python -m compileall -q backend/app frontend/streamlit`, `bash -n`
  dos scripts alterados e `git diff --check` → passaram.
- Streamlit AppTest executado pelo agente em app.py e páginas1–4:0 exceptions.
- Navegador real em loopback: criar demo→resultado persistido, origem mock explícita,
  foco por Tab, viewport1280×720 e390×844; modo real de teste bloqueia demo, mantém
  etiqueta do histórico; backend desligado mostra erro. Ver [evidências](implementation/verification.md).

## Limites e gates

O reviewer independente identificou falhas concretas em captura, confirmação, sessão e
persistência; foram corrigidas com regressões. Os dois últimos P2 de firmware foram
revalidados por outro agente e resolvidos. Isso não equivale a certificação do hardware.

ESP-IDF build não executou: `esp-idf/export.sh` ausente. O alvo não foi escolhido;
defaults de S3/flash/PSRAM do esboço foram removidos para não impor hardware. Sanitizers
host foram tentados pelo reviewer e ficaram sem retorno por60s: inconclusivos, não PASS.
Whisper real/modelos não foram instalados/baixados/executados; não há benchmark.

Gates locais do Flow: evidência TDD estruturada passou após corrigir timestamp copiado
incorretamente do registro ASR. O RED inicial do firmware foi ausência de API/compilação,
**não prova de TDD comportamental**; regressões posteriores observaram falhas de comportamento.
Doctor/runner foram inicializados, mas a cadeia completa não foi executada. UI strict
continua FAIL por preflight/registro estruturado de automação/design, apesar da navegação
real e screenshots. Security gate FAIL porque trata os dois `.env.example` exigidos como
`.env`; gitleaks/semgrep/trivy não estavam disponíveis e não foram executados. Os exemplos
foram revisados e contêm somente defaults/placeholders. Não se declara `ready-for-review`
pelos gates completos do Flow nem prontidão de produção.

O runtime `.codex/` foi materializado apenas localmente como ferramenta; não é mudança
na distribuição Codex/Kiro/Claude e não será publicado. Os documentos deste projeto e
esta evidência são versionados. Não houve persistência externa em Notion/Obsidian
comprovada; nenhuma alegação de autosync remoto.

## Próximos passos necessários

Seguir [instalação](../README.md), [migração/rollback](data_model.md),
[contrato serial](iot_protocol.md), [método de fala](speech-validation.md) e
[roteiro real de mesa](manual-validation.md). Decidir se o candidato lexical local é
suficiente ou selecionar outro extrator em tarefa separada; não há serviço contratado.
Preservar bancos/journal/áudios fora do Git. Commits e SHA de publicação são informados
na resposta de entrega depois da conferência remota, não presumidos por este documento.

## Publicação

A tentativa de `git push origin HEAD:refs/heads/feat/nekomind-touch-mac-mvp` foi
recusada pelo GitHub com HTTP403 para a conta autenticada. Isso foi verificado neste
ambiente, independentemente da tentativa histórica pelo Notion. Nenhum destes commits
foi publicado por esta execução. A conferência com `git ls-remote` manteve a feature
e main em `0a4bdfb4278858bd7e10ec69f7825ba1ebdcdafd`.

Os três commits locais podem ser transportados pelo bundle entregue com a resposta.
Após obter acesso de escrita ao repositório, conferir `git fetch origin` e integrar
qualquer avanço remoto preservando os commits; então repetir push normal somente para
a feature branch. Não usar reset, force-push ou merge em main para contornar a permissão.
