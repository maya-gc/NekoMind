# NekoMind Backend

API FastAPI que recebe o áudio do dispositivo ESP32-S3, transcreve (ASR),
extrai tópicos (LLM), calcula métricas heurísticas e persiste em SQLite.

## Rodando

```bash
# Na raiz do repositorio:
bash scripts/setup_backend.sh   # ou scripts\setup_backend.ps1 no Windows
bash scripts/run_backend.sh     # ou scripts\run_backend.ps1
```

API em `http://127.0.0.1:8000` — documentação interativa em `/docs`.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | status do serviço |
| POST | `/api/v1/sessions` | inicia sessão |
| POST | `/api/v1/sessions/{id}/audio` | envia chunk de áudio (multipart) |
| POST | `/api/v1/sessions/{id}/finish` | finaliza e dispara a análise |
| GET | `/api/v1/sessions` | lista sessões |
| GET | `/api/v1/sessions/{id}` | detalhe (tópicos + métricas) |
| GET | `/api/v1/dashboard/summary` | agregados do dashboard |
| WS | `/ws/device` | canal do dispositivo (JSON do protocolo) |

Contratos com exemplos: `docs/api_contract.md`.

## Modo mock (padrão)

Sem chave de API e sem baixar modelos: ASR e LLM retornam dados fictícios
marcados como `[DEMO]`. Para IA real, veja `app/adapters/asr_adapter.py`
(faster-whisper) e `app/adapters/llm_adapter.py` e o arquivo `.env.example`.

## Testes

```bash
bash scripts/run_tests.sh   # pytest com SQLite temporário isolado
```

## Arquitetura em camadas

- `app/api/` — rotas: validação de entrada/saída (Pydantic);
- `app/services/` — casos de uso (ingestão, processamento, análise);
- `app/repositories/` — acesso ao banco (SQLAlchemy);
- `app/database/` — engine, sessões e modelos;
- `app/adapters/` — serial, Wi-Fi, ASR e LLM (substituíveis).
