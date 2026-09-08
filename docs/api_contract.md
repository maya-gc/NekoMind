# Contrato da API

Base URL: `http://127.0.0.1:8000` — documentação interativa em `/docs`
(OpenAPI). Todas as respostas são JSON.

## Health

### `GET /health`

```json
{
  "status": "ok",
  "service": "nekomind-backend",
  "asr_provider": "mock",
  "llm_provider": "mock"
}
```

## Sessões

### `POST /api/v1/sessions` — criar sessão

Corpo (opcional):
```json
{ "title": "Fotossíntese" }
```

`201 Created`:
```json
{
  "id": 1,
  "title": "Fotossíntese",
  "started_at": "2026-09-05T12:00:00Z",
  "ended_at": null,
  "duration_seconds": 0.0,
  "status": "recording",
  "transcription": null,
  "clarity_score": null,
  "is_demo": false
}
```

### `GET /api/v1/sessions` — listar

`?limit=100&offset=0` → array de `SessionOut`.

### `GET /api/v1/sessions/{id}` — detalhe

`200` → `SessionOut` + `topics` e `metrics`:

```json
{
  "id": 1,
  "title": "Fotossíntese",
  "started_at": "2026-09-05T12:00:00Z",
  "ended_at": "2026-09-05T12:02:30Z",
  "duration_seconds": 150.0,
  "status": "completed",
  "transcription": "[DEMO] Transcrição simulada: ...",
  "clarity_score": 7.3,
  "is_demo": true,
  "topics": [
    { "id": 1, "session_id": 1, "name": "fotossintese", "relevance": 0.95, "notes": "[DEMO] ..." }
  ],
  "metrics": [
    { "id": 1, "session_id": 1, "name": "word_count", "value": 240.0, "unit": "words" }
  ]
}
```

`404` quando não existe.

### `POST /api/v1/sessions/{id}/audio` — enviar chunk (multipart)

Campos:
- `file`: arquivo binário (PCM 16 bits mono por padrão);
- `sequence`: int (ordem do chunk);
- `audio_format` (opcional, `pcm_s16le`);
- `sample_rate` (opcional, `16000`).

`201 Created`:
```json
{ "chunk_id": 10, "session_id": 1, "sequence": 0, "byte_size": 64000 }
```

### `POST /api/v1/sessions/{id}/finish` — finalizar e analisar

Dispara o pipeline (junta áudio → ASR → tópicos → métricas). Retorna o
detalhe completo da sessão. `404` se a sessão não existir.

## Dashboard

### `GET /api/v1/dashboard/summary`

```json
{
  "total_sessions": 12,
  "total_study_seconds": 3650.5,
  "avg_clarity_score": 6.8,
  "top_topics": [["fotossintese", 5], ["celula", 3]]
}
```

## WebSocket

### `WS /ws/device`

Canal do dispositivo. Cliente envia mensagens do protocolo JSON
(docs/iot_protocol.md) já em JSON:
- `session_start` → resposta `ack` com `session_id`;
- `audio_chunk` (com `data` em base64) → `ack`;
- `session_end` → análise e resposta `analysis_result`;
- `device_status` → `ack`.

Respostas: `{"type":"ack", ...}`, `{"type":"analysis_result", ...}` ou
`{"type":"error", "detail": "..."}`.

## Erros

Formato padrão (FastAPI/HTTP):
```json
{ "detail": "Sessão não encontrada" }
```