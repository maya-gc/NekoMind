# NekoMind Backend

API FastAPI que recebe o áudio capturado no Mac, sob controle do touch no
ESP32-S3, transcreve (ASR), extrai tópicos (LLM), calcula métricas heurísticas
e persiste em SQLite.

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

## Voz local da gatinha no Mac (opcional)

No macOS com Apple Silicon, prepare uma vez o Kokoro `pf_dora` em português
brasileiro:

```bash
bash scripts/setup_voice_mac.sh
```

O script instala as dependências opcionais no `backend/.venv`, baixa os pesos e
confirma que o modelo abre sem rede. Para ativar, use
`NEKOMIND_TTS_PROVIDER=kokoro` em `backend/.env` ou passe `--voice kokoro` ao
iniciar `python -m app.mac`. A saída usa o alto-falante selecionado no Mac, via
`afplay`; o ESP32 continua recebendo apenas estados pela serial. A voz fala ao
ficar pronto, ao pausar, ao fazer a pergunta e dar a dica solicitada, e ao
comparar as duas respostas. Iniciar ou retomar a
gravação interrompe a voz, evitando que ela entre na própria transcrição.

O fluxo de missão, dica e segunda resposta está em
[`docs/interactive-dialogue.md`](../docs/interactive-dialogue.md).

O carregamento e a síntese acontecem localmente depois do primeiro download.
O modo `off` mantém o bridge sem dependências de voz. O modelo é
[Apache 2.0](https://huggingface.co/hexgrad/Kokoro-82M); não há custo por
fala gerada.

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
