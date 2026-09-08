# Protocolo do dispositivo (JSON Lines)

## Visão geral

O firmware se comunica com o computador enviando **uma mensagem JSON por
linha** (JSON Lines, `\n` terminado) via **USB serial** (UART/USB-JTAG,
115200 baud por padrão). O mesmo formato é aceito pelo WebSocket
`/ws/device` do backend (lá, cada mensagem é um JSON).

Encoding: UTF-8. Campos desconhecidos devem ser ignorados.

## Tipos de mensagem (device → computador)

### `session_start`

Avisa o início de uma sessão de gravação.

```json
{
  "type": "session_start",
  "session_id": "demo-0001",
  "sample_rate": 16000,
  "format": "pcm_s16le",
  "title": "Fotossíntese"
}
```

### `audio_chunk`

Um bloco de áudio PCM. No MVP o payload é anunciado em stub; na versão
final `data` virá em base64.

```json
{
  "type": "audio_chunk",
  "session_id": "demo-0001",
  "seq": 3,
  "bytes": 4096,
  "sample_rate": 16000,
  "encoding": "none-stub",
  "data": "..."
}
```

### `session_end`

Sinaliza fim da gravação.

```json
{
  "type": "session_end",
  "session_id": "demo-0001"
}
```

### `device_status`

Telemetria periódica (estado do avatar, memória, simulação).

```json
{
  "type": "device_status",
  "state": "RECORDING",
  "free_heap": 240000,
  "simulated": 1
}
```

### `error`

Falha de captura, comunicação ou processamento.

```json
{
  "type": "error",
  "where": "capture",
  "code": "I2S_READ_FAILED"
}
```

## Tipos de mensagem (computador → device)

### `analysis_result`

Resultado da análise de uma sessão (enviada via WebSocket quando o
dispositivo estiver conectado por esse canal).

```json
{
  "type": "analysis_result",
  "session_id": 12,
  "status": "completed",
  "clarity_score": 7.3,
  "summary": "Você cobriu 3 tópicos..."
}
```

## Estados → mensagens (referência)

| Estado | Mensagens típicas |
|---|---|
| IDLE | `device_status` (estado idle) |
| RECORDING | `session_start`, `audio_chunk` |
| SENDING | `audio_chunk` (envio em andamento) |
| PROCESSING | `session_end` |
| SUCCESS | recebe `analysis_result` |
| ERROR | `error` |

## Notas de implementação

- O firmware ainda envia chunks em modo **stub** (metadados sem payload)
  para não poluir o console durante o MVP.
- Quando a serial for ligada ao backend, o adaptador
  `backend/app/adapters/serial_adapter.py` fará o parsing destas linhas.
- O transport Wi-Fi (futuro) usará o mesmo formato JSON sobre TCP/WebSocket.