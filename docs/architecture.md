# Arquitetura do NekoMind

## Visão geral

```mermaid
flowchart LR
    subgraph Device["Dispositivo (ESP32-S3)"]
        MIC[INMP441<br/>microfone digital] -->|I2S + DMA| FW[Firmware NekoMind]
        FW -->|estado do avatar| LCD[LCD]
    end

    FW -->|JSON Lines<br/>serial USB| BE[Backend FastAPI]
    FW -.->|Wi-Fi TCP/WebSocket<br/>futuro| BE

    subgraph Backend["Backend (Python 3.11+)"]
        API[Rotas /api/v1 + /ws/device]
        SRV[Serviços: ingestão, transcrição,<br/>tópicos, métricas]
        REPO[Repositórios]
        ASR[ASRAdapter<br/>mock / faster-whisper]
        LLM[LLMAdapter<br/>mock / API externa]
    end

    BE --> DB[(SQLite<br/>MVP)]
    DB -.-> PG[(PostgreSQL<br/>futuro)]
    ASR --> BE
    LLM --> BE

    FR[Frontend Streamlit] -->|HTTP API| API
```

## Fluxo de uma sessão

```mermaid
sequenceDiagram
    participant E as ESP32-S3
    participant B as Backend
    participant A as ASR/LLM (mock)
    participant D as SQLite

    E->>B: session_start
    loop cada chunk
        E->>B: audio_chunk (base64 / multipart)
        B->>D: grava chunk + metadados
    end
    E->>B: session_end
    B->>B: junta áudio -> WAV
    B->>A: transcreve (transcrição [DEMO])
    B->>A: extrai tópicos
    B->>B: calcula métricas heurísticas
    B->>D: persiste transcrição, tópicos, métricas
    B-->>E: analysis_result (WebSocket)
    FR->>B: GET /api/v1/dashboard/summary
    B->>D: consulta agregados
    B-->>FR: resumo do dashboard
```

## Componentes

### IoT (firmware)

- `main/nekomind_main.c` — ponto de entrada;
- `session_controller` — máquina de estados da sessão;
- `audio_capture` — buffer circular de chunks PCM;
- `i2s_microphone` — driver INMP441 (I2S + DMA);
- `audio_transport` — serial JSON Lines (Wi-Fi planejado);
- `avatar_state` — estados IDLE/RECORDING/SENDING/PROCESSING/SUCCESS/ERROR;
- `display_ui` — renderização do avatar no LCD (ou log no MVP).

Protocolo: [`docs/iot_protocol.md`](iot_protocol.md).

### Backend

Camadas isoladas:

| Camada | Pasta | Responsabilidade |
|---|---|---|
| API | `app/api/` | rotas e validação (Pydantic) |
| Serviços | `app/services/` | casos de uso |
| Repositórios | `app/repositories/` | acesso ao banco |
| Banco | `app/database/` | engine, modelos, sessões |
| Adaptadores | `app/adapters/` | serial, Wi-Fi, ASR, LLM |
| Schemas | `app/schemas/` | contratos de entrada/saída |

Decisões:

- **SQLite por padrão** (arquivo local, zero setup); troca por PostgreSQL
  é só mudar `NEKOMIND_DATABASE_URL`.
- **Adapters substituíveis**: `MockASRAdapter`/`MockLLMAdapter` (padrão,
  offline) com pontos de extensão para faster-whisper e APIs de LLM.
- **Métricas heurísticas** em `services/clarity_evaluation.py`, cada uma
  documentada e explicável.

### Frontend

- Streamlit; consumo exclusivamente via `services/backend_client.py`.
- Páginas: Dashboard, Sessões, Tópicos, Configurações.

## Segurança e configuração

- Chaves de API apenas via `.env` (nunca versionado).
- Configurações centralizadas em `backend/app/config.py` (prefixo
  `NEKOMIND_`).

## Limitações do MVP

- ASR/LLM em modo mock (dados `[DEMO]`).
- Firmware com captura e LCD simulados.
- Serial ainda não conectada ao backend (upload via API/WebSocket).
- Sem autenticação (uso local/didático).