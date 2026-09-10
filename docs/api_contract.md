# API local

Base `http://127.0.0.1:8000`; documentação executável em `/docs` e `/openapi.json`.
Somente loopback, um worker, sem reload. Não há autenticação para exposição em rede.
O bridge usa HTTP local e serial; `/ws/device` legado responde
`legacy_transport_disabled` e fecha1008, sem aceitar áudio embarcado.

## Criar e consultar

`POST /api/v1/sessions` recebe:

```json
{"title":"Sessao touch","request_id":"bootNonce-1","capture_source":"mac_microphone"}
```

`device_session_id` é opcional. HTTP201, inclusive replay de criação. `request_id`
confere unicidade de início no banco: mesmo payload retorna mesma sessão, divergente409,
inclusive concorrência. O modo/provedores vêm da configuração validada do backend.
Clientes HTTP antigos podem omitir id, perdendo idempotência de início; bridge sempre envia.

`GET /api/v1/sessions`, `GET /api/v1/sessions/{id}` e
`GET /api/v1/dashboard/summary` oferecem histórico, detalhe e agregados heurísticos.
`GET /health` informa `mode`, `asr_provider`, `llm_provider`; health não carrega modelo
nem comprova disponibilidade física do microfone/modelo.

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

`POST /api/v1/sessions/{id}/finish`, corpo opcional `{"request_id":"bootNonce-4"}`.
A primeira chamada adquire processing atomicamente e executa o pipeline. Concorrente
retorna HTTP200 com processing; posteriores devolvem estado/resultado existente,
sem duplicar análise, tópicos ou métricas. Nova tentativa exige criar nova sessão.
Não presumir que HTTP200 implica conclusão. Consultar GET após timeout de rede.

Primeira rejeição de captura retorna422 com SessionDetail em error; falha inesperada
de análise retorna500 com erro persistido sanitizado. Reconsulta retorna200 com estado
error existente. Id inexistente404. Configuração inválida bloqueia startup.

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

## Extrator candidato

`local_keywords` é opt-in e executa extração lexical local sobre a transcrição validada,
com frases literalmente presentes, máximo8, sem completar quantidade. Relevância é
pontuação lexical, não certeza. Provedor/modelo definitivo permanece decisão aberta.
Adaptadores inválidos ou indisponíveis falham explicitamente; nenhuma chamada de nuvem.
