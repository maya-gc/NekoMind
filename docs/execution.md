# Execução e evidência

Backend local:

```bash
PYTHON_BIN=python3.12 bash scripts/setup_backend.sh
backend/.venv/bin/python -m pip install -r backend/requirements-mac.txt
cp -n backend/.env.example backend/.env
bash scripts/run_backend.sh
```

Bridge físico no Mac:

```bash
cd backend
.venv/bin/python -m serial.tools.list_ports
.venv/bin/python -m sounddevice
.venv/bin/python -m app.mac --port /dev/cu.PORTA_ESCOLHIDA
```

Bridge demo operacional sem serial/microfone físico:

```bash
cd backend
.venv/bin/python -m app.mac --simulate
```

Os resultados finais de testes e QA ficam em `docs/qa-report.md`. Este guia descreve
como executar o sistema localmente; ele não declara aprovação visual ou prontidão física.

Grupos esperados: backend, frontend web, Streamlit, firmware host, lint/compile,
integração com fakes, QA visual 240x320, 320x240, notebook e TV. Se modelo ASR local,
microfone físico ou ESP32/display não estiverem disponíveis, registrar como não executado.
