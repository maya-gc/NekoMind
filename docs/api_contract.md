# API local

Base `http://127.0.0.1:8000`; documentação executável em `/docs` e `/openapi.json`.
Somente loopback, um worker, sem reload. O backend cria `storage/operator-token`
com permissão `0600`; rotas privadas exigem `Authorization: Bearer <token>`.
Não colocar o token em URL, logs, fixtures ou Git. O bridge usa HTTP local e serial;
`/ws/device` legado responde
`legacy_transport_disabled` e fecha1008, sem aceitar áudio embarcado.

Rotas públicas locais sem token: `/health`, `/api/v1/experience/public`, `/public`.
Rotas reservadas ao operador local: `/api/v1/sessions`, `/api/v1/audio`,
`/api/v1/experience/presenter`, `/api/v1/experience/commands`,
`/api/v1/experience/bridge`, `/api/v1/experience/providers`, `/touch` como emulador
com comandos após token em memória e `/presenter`.

## Criar e consultar

`POST /api/v1/sessions` recebe:

```json
{"title":"Sessao touch","request_id":"bootNonce-1","capture_source":"mac_microphone"}
```

`device_session_id` é opcional. HTTP201, inclusive replay de criação. `request_id`
confere unicidade de início no banco: mesmo payload retorna mesma sessão, divergente409,
inclusive concorrência. O modo/provedores vêm da configuração validada do backend.
Após excluir uma sessão, seu identificador não é reutilizado e reenviar o request_id
de início devolve HTTP410. O tombstone conserva apenas IDs, sem conteúdo da sessão.
Clientes HTTP antigos podem omitir id, perdendo idempotência de início; bridge sempre envia.

`GET /api/v1/sessions`, `GET /api/v1/sessions/{id}` e
`GET /api/v1/dashboard/summary` oferecem histórico, detalhe e agregados heurísticos.
`GET /health` informa `mode`, `asr_provider`, `llm_provider`; health não carrega modelo
nem comprova disponibilidade física do microfone/modelo.

`PATCH /api/v1/sessions/{id}/subject` recebe `{"subject":"biologia","confirmed":true}`.
`GET /api/v1/history/subjects/{subject}` retorna pontos locais comparáveis somente
entre sessões completadas do mesmo assunto confirmado e mesmo método de métrica.
Tendência numérica não é prova de domínio.

## Captura

`POST /api/v1/sessions/{id}/capture-state` recebe `state` igual a recording/paused/error,
mais `error_code`/`error_message` opcionais. Estado terminal/processing não regride;
UPDATE condicional garante isso mesmo com concorrência. O corpo devolve o estado
persistido: cliente deve conferir id/status, não tratar qualquer HTTP200 como confirmação.
O campo legado `request_id` é aceito aqui, mas deduplicação de pause/resume é do journal
serial do bridge; a API garante transição de estado, não recibos individuais de captura.

`POST /api/v1/sessions/{id}/audio` recebe multipart `file`, `sequence` (>=0),
`audio_format=pcm_s16le`, `sample_rate=16000`. PCM16 mono, tamanho par, não vazio;
máximo960000 bytes por chunk (30s). Resposta201 com chunk_id/session_id/sequence/byte_size.
Replay idêntico retorna200 e `deduplicated=true`; divergente/lacuna/estado fechado409,
formato inválido422, vazio400, excessivo413. Apenas recording/paused aceitam upload.

## Finalizar

`POST /api/v1/sessions/{id}/cancel`, corpo `{"confirmed":true}`, cancela uma
sessão ativa/recuperável sem permitir que um worker tardio reverta o cancelamento.
Repetir cancelamento devolve o estado existente; resultado já concluído é preservado.

`POST /api/v1/sessions/{id}/finish`, corpo opcional `{"request_id":"bootNonce-4"}`.
A primeira chamada adquire processing atomicamente e executa o pipeline. Concorrente
retorna HTTP200 com processing; posteriores devolvem estado/resultado existente,
sem duplicar análise, tópicos ou métricas. Nova tentativa exige criar nova sessão.
Não presumir que HTTP200 implica conclusão. Consultar GET após timeout de rede.

Primeira rejeição de captura retorna422 com SessionDetail em error; falha inesperada
de análise retorna500 com erro persistido sanitizado. Reconsulta retorna200 com estado
error existente. Id inexistente retorna404. Configuração inválida bloqueia startup.

`POST /api/v1/sessions/{id}/recover` recebe `action=resume|analyze|discard` e
`request_id` opcional. `resume` deixa a sessão aguardando retomada explícita; não abre
microfone sozinho. `analyze` reaproveita transcrição persistida quando possível.
Se a sessão já está `completed` com `error_code=audio_cleanup_failed`, `analyze` só
repete a limpeza de áudio pendente e não reexecuta análise.
`discard` remove a sessão recuperável confirmada. `DELETE /api/v1/sessions/{id}`
exige `{"confirmed":true}` e rejeita sessões ativas/recuperáveis pela rota comum de
exclusão.

Campos importantes de SessionDetail:

- `id`, `status`, `is_demo`, `mode`, `start_request_id`, `finish_request_id`.
- `transcription`, `duration_seconds`, `clarity_score` (heurístico, pode ser null).
- `asr_provider_used`, `topic_provider_used`, `analysis_origin`.
- `audio_validation` (JSON textual WebRTC quando executado); `speech_validation`
  permanece campo de compatibilidade e pode ser null.
- `error_code`, `error_message`, `topics`, `metrics`.

Topics contêm `session_id`, `name`, `relevance`, `notes`; sem mock no modo real.
Somente `completed` com tipo, id, origem e tópicos válidos vira resultado serial.
ASR concluído antes de falha na extração mantém origem registrada, mas não gera
conclusão parcial. Ausência de fala não produz nota nem assuntos fictícios.

## Extrator lexical local

`local_keywords` é opção explícita e executa extração lexical local sobre a transcrição
validada, com frases literalmente presentes, máximo8, sem completar quantidade.
Relevância é pontuação lexical, não certeza. Adaptadores inválidos ou indisponíveis
falham explicitamente; nenhuma chamada de nuvem.

## Experiência feira

`GET /api/v1/experience/public` devolve snapshot sanitizado para TV/público: estado,
modo real/demo, diagnóstico resumido, jornada, voz compacta enquanto grava, resultado
público, erro seguro, recuperação e conexão do bridge. A consulta é estritamente
read-only. Não expõe transcrição completa, áudio, token, caminhos locais ou comandos
administrativos.

`GET /api/v1/experience/presenter` exige token e adiciona `available_actions` e
metadados seguros de sessões recuperáveis. `POST /api/v1/experience/commands` exige
token, `request_id`, comando e confirmação para `cancel`, `discard` e `reset`.
O backend carimba a `generation` atual ao enfileirar o comando. `GET
/api/v1/experience/commands` é consumido pelo bridge; `GET /commands/{rid}` permite
ao frontend consultar recibo do comando. `POST /commands/{rid}/ack` confirma resposta
serial com geração e sessão reconciliadas para ações destrutivas.
`POST /api/v1/experience/bridge` publica estado confirmado do Mac e agenda reset por
inatividade no heartbeat autenticado. O backend rejeita `completed` sem `StudySession`
completed válido e rejeita `recording/paused` sem reconciliação de sessão.

`GET /api/v1/experience/providers` executa autoteste local: backend sempre deve
responder; ASR mock é `skipped`; ASR real tenta disponibilidade local sem baixar modelo;
o extrator de tópicos executa uma frase curta e informa `local_keywords`, `mock`,
`skipped` ou erro.
