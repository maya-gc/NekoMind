# Requisitos do NekoMind

## Visão

Sistema embarcado + web que apoia o estudante a aplicar a técnica Feynman:
explicar um conceito em voz alta e receber feedback sobre clareza e
abrangência da explicação.

## Requisitos funcionais

### Firmware (ESP32-S3)

| ID | Requisito |
|---|---|
| FR-IOT-01 | Capturar áudio do microfone INMP441 via I2S com DMA. |
| FR-IOT-02 | Bufferizar áudio PCM mono em chunks de tamanho fixo. |
| FR-IOT-03 | Enviar chunks ao computador via USB serial (JSON Lines). |
| FR-IOT-04 | Exibir o estado da sessão no LCD por um avatar lúdico. |
| FR-IOT-05 | Modelar estados: IDLE, RECORDING, SENDING, PROCESSING, SUCCESS, ERROR. |
| FR-IOT-06 | Enviar mensagens de status/telemetria. |
| FR-IOT-07 | (Futuro) Alternar transporte para Wi-Fi. |
| FR-IOT-08 | Pinos, sample rate, chunk size e Wi-Fi centralizados em configuração. |

### Backend

| ID | Requisito |
|---|---|
| FR-BE-01 | Receber e persistir sessões de estudo (início/fim, status). |
| FR-BE-02 | Receber chunks de áudio (multipart) e via WebSocket. |
| FR-BE-03 | Transcrever áudio (ASR) com adaptador substituível (mock por padrão). |
| FR-BE-04 | Extrair tópicos/conceitos (LLM) com adaptador substituível (mock). |
| FR-BE-05 | Calcular métricas: duração, palavras, nº de tópicos, diversidade lexical, cobertura e clareza. |
| FR-BE-06 | Persistir em SQLite (PostgreSQL preparado via URL). |
| FR-BE-07 | Expor endpoints REST: /health, sessões, áudio, finish, dashboard/summary. |
| FR-BE-08 | Expor WebSocket /ws/device para o dispositivo. |
| FR-BE-09 | Rodar integralmente sem chaves de API e sem baixar modelos de IA. |
| FR-BE-10 | Marcar dados gerados por adapters mock como demonstração ([DEMO]). |

### Frontend

| ID | Requisito |
|---|---|
| FR-FE-01 | Dashboard: total de sessões, tempo estudado, clareza média, tópicos. |
| FR-FE-02 | Listar e detalhar sessões, exibir transcrição e cards de métricas. |
| FR-FE-03 | Exibir avatar com estados espelhando o firmware. |
| FR-FE-04 | Tela de configurações (URL do backend e modo demonstração). |
| FR-FE-05 | Consumir somente a API do backend (nunca o banco diretamente). |

## Requisitos não funcionais

| ID | Requisito |
|---|---|
| FR-NF-01 | Backend em Python 3.11+ com FastAPI. |
| FR-NF-02 | Frontend Streamlit em http://127.0.0.1:8501; backend em http://127.0.0.1:8000. |
| FR-NF-03 | Ferramentas locais dentro do monorepo (ESP-IDF, tools, VS Code portátil). |
| FR-NF-04 | Sem instalações globais de toolchain/IDE quando houver alternativa local. |
| FR-NF-05 | Não versionar binários pesados, venvs, builds, .env (ver .gitignore). |
| FR-NF-06 | Não expor chaves de API. |
| FR-NF-07 | Latência alvo: captura e envio de chunks em tempo quase real no MVP. |
| FR-NF-08 | Projeto compilável e executável com IA em modo mock (demonstração). |
| FR-NF-09 | Testes automatizados básicos (health, sessão, persistência). |

## Fora de escopo no MVP

- Avaliação pedagógica definitiva (métricas são heurísticas).
- Autenticação/autorização.
- Suporte multi-dispositivo simultâneo.
- PostgreSQL ativo (apenas preparado).
- ASR/LLM reais (apenas pontos de extensão).