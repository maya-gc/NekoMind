# Log de setup do NekoMind

Registro do que foi criado, instalado e validado, incluindo falhas e
soluções. Data: 2026-09-05.

## Ambiente

- SO: Windows (PowerShell 5.1); Área de Trabalho em `C:\Users\mayac\Desktop`.
- Raiz do projeto: `C:\Users\mayac\Desktop\nekomind`.
- Python 3.13 (sistema) + Git 2.55.0 (Git for Windows) disponíveis.

## Estrutura criada

Monorepo com:

- `iot/nekomind_firmware/` — esqueleto ESP-IDF para ESP32-S3 (7 módulos C:
  main, audio_capture, i2s_microphone, audio_transport, display_ui,
  avatar_state, session_controller), com máquina de estados
  IDLE/RECORDING/SENDING/PROCESSING/SUCCESS/ERROR, configurações de
  hardware marcadas como TODO e captura/LCD simulados por logs.
- `backend/` — FastAPI com camadas api/services/repositories/database/
  schemas/adapters; SQLite via SQLAlchemy; adapters ASR e LLM em modo
  mock ([DEMO]); endpoints de /health, sessões, áudio, finish, dashboard
  e WebSocket /ws/device; testes pytest (health, sessão, persistência).
- `frontend/streamlit/` — dashboard com 4 páginas, avatar-gato (CSS/emoji),
  cards de métricas, gráficos e configurações; consome só a API.
- `docs/` — architecture, requirements, api_contract, data_model,
  iot_protocol, setup-log, README.
- `scripts/` — 9 scripts `.sh` + 9 `.ps1` (setup, execução, testes, VS Code).
- `.vscode/` — settings, tasks, launch, extensions para ESP-IDF + Python.
- `vscode-portable/` — VS Code 1.136.1 portátil com `data/` e extensões.
- `esp-idf/` + `tools/` — ESP-IDF v5.3.1 e toolchains (não versionados).

## Dependências instaladas

### VS Code portátil (dentro de `vscode-portable/`)

- VS Code 1.136.1 (win32-x64 archive), modo portátil com `data/`.
- Extensões em `vscode-portable/data/extensions`:
  espressif.esp-idf-extension, ms-vscode.cpptools, ms-vscode.cmake-tools,
  ms-vscode.cpp-devtools, ms-python.python, ms-python.vscode-pylance,
  ms-python.debugpy, ms-python.vscode-python-envs,
  llvm-vs-code-extensions.vscode-clangd, usernamehw.errorlens,
  eamodio.gitlens.

### ESP-IDF (dentro de `esp-idf/` e `tools/`)

- ESP-IDF v5.3.1 (branch v5.3.1, shallow clone com submódulos).
- `tools/` com IDF_TOOLS_PATH local: cmake, ninja, ccache, xtensa-esp-elf,
  riscv32-esp-elf, openocd-esp32, esp-rom-elfs, python_env
  (idf5.3_py3.13_env), etc.

### Dependências Python (backend/frontend)

- **Não instaladas nesta execução** (opção do usuário: validar depois).
- Os scripts `setup_backend.sh/.ps1` e `setup_frontend.sh/.ps1` criam os
  venvs (`backend/.venv`, `frontend/streamlit/.venv`) e instalam
  `requirements.txt`.

## Validações realizadas

| Item | Resultado |
|---|---|
| Estrutura do monorepo | OK (árvore completa conforme especificação) |
| Sintaxe Python (backend + frontend) | OK (py_compile em todos os .py) |
| JSON (.vscode + frontend config) | OK (parse válido) |
| Sintaxe dos scripts `.sh` | OK (`bash -n` em todos) |
| Build do firmware (ESP-IDF, alvo esp32s3) | OK — `nekomind_firmware.bin` gerado |
| Backend `GET /health` | Pendente (dependências não instaladas) |
| Frontend (Streamlit) iniciar | Pendente (dependências não instaladas) |
| Testes pytest do backend | Pendente (dependências não instaladas) |
| Git | Não inicializado (opção do usuário) |

Para concluir as validações pendentes, executar:

```powershell
# Backend
.\scripts\setup_backend.ps1
.\scripts\run_backend.ps1          # http://127.0.0.1:8000/health
.\scripts\run_tests.ps1

# Frontend
.\scripts\setup_frontend.ps1
.\scripts\run_frontend.ps1         # http://127.0.0.1:8501
```

## Como executar

```powershell
# Tudo de uma vez (backend + frontend):
.\scripts\run_all.ps1

# Individual:
.\scripts\run_backend.ps1
.\scripts\run_frontend.ps1
.\scripts\run_tests.ps1

# VS Code portátil:
.\scripts\launch_vscode.ps1

# Firmware (após definir pinos nos headers):
.\scripts\setup_espidf_portable.ps1   # já executado
.\scripts\source_idf.ps1
cd iot\nekomind_firmware
idf.py set-target esp32s3
idf.py build
idf.py -p COM5 flash monitor
```

## Pendências de hardware

| Item | Local | Estado |
|---|---|---|
| Pinos I2S do INMP441 (BCLK/WS/DIN) | `iot/nekomind_firmware/main/i2s_microphone.h` | TODO — definir |
| Pinos do LCD (MOSI/CLK/CS/DC/RST/BL) | `iot/nekomind_firmware/main/display_ui.h` | TODO — definir |
| Driver real de captura I2S/DMA | `i2s_microphone.c` | Stub (simulado) |
| Driver real do LCD + renderização do avatar | `display_ui.c` | Stub (log) |
| Payload real do `audio_chunk` (base64) | `audio_transport.c` | Stub |
| Wi-Fi (SSID/senha/host/porta) | `audio_transport.h` | TODO — não versionar credenciais |
| Ligação serial firmware ↔ backend | `backend/app/adapters/serial_adapter.py` | Ponto de extensão |

## Erros encontrados e soluções

1. **VS Code não abria após extração**
   - Erro: `Invalid file descriptor to ICU data` e path `a44adf7f53/...`
     inexistente no `bin/code.cmd`.
   - Causa: a extração do ZIP do VS Code criou uma pasta de payload
     versionada (`a44adf7f53/`); os scripts `bin/code` referenciam essa
     pasta. Uma reorganização manual quebrou o layout.
   - Solução: restaurar o layout original (payload `a44adf7f53/` + raiz)
     e validar com `Code.exe --version` (1.136.1 OK).

2. **`idf.py set-target` falhava com "cmake must be available on the PATH"**
   - Causa: o ambiente ESP-IDF (export) precisa ser carregado antes.
   - Solução: executar build dentro de um shell que roda `export.ps1`
     antes; build concluído com sucesso.

3. **ExecutionPolicy bloqueava `export.ps1`**
   - Causa: política de execução do PowerShell desabilitada.
   - Solução: usar `powershell -ExecutionPolicy Bypass` nos scripts de
     validação; o `run_all.ps1`/`launch_vscode.ps1` documenta o uso.

4. **Pydantic `str(status)` de enum**
   - Detalhe: `SessionOut.status` vinha de um `Enum`; serialização
     incorreta. Adicionado `field_validator` para converter ao `.value`.

5. **Lifespan cria storage após init_db**
   - Detalhe: ordem trocada podia falhar em clone limpo (sem `storage/`).
   - Solução: criar `storage_dir` antes de `init_db()`.

## Observações

- **Git não inicializado** por opção do usuário; `.gitignore` já está
  preparado (ignora esp-idf/, tools/, vscode-portable/, venvs, builds,
  bancos SQLite, .env, logs).
- Nenhuma chave de API foi criada ou versionada; modo mock é o padrão.
- A IA (ASR/LLM) é apoio à reflexão, não avaliação definitiva; métricas
  são heurísticas.