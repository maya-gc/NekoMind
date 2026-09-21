# NekoMind Touch Lab

Plataforma local para desenvolver, testar, calibrar, controlar e demonstrar o
LCD ILI9341 240×320 + touch XPT2046 do **ESP32-S3-DevKitC-1** junto ao fluxo
**NekoMind** — com firmware PlatformIO (driver próprio `ILI9341_Driver`),
aplicação web local (FastAPI), emulador visual, protocolo serial JSON Lines,
testes automatizados e documentação técnica.

> **Verdade acima de tudo:** nada aqui afirma validação física do touch sem
> teste na unidade real. Simulação é sempre rotulada como simulação
> (`docs/risks.md` traz a checklist de validação física).

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `include/` | Configurações de placa e protocolo (`BoardConfig.h` **sem** GPIO48/backlight) |
| `src/` | Firmware: main, protocolo serial, sessão NekoMind, UI kawaii |
| `lib/neko_core` | Lógica pura em C++ (calibração, filtros, debounce, estados, protocolo, layout) |
| `lib/neko_display` | Driver ILI9341 (baseline validado) + fonte 5×7 |
| `lib/neko_touch` | TouchManager (XPT2046, polling, NVS) |
| `firmware/` | Snapshot de proveniência do baseline + notas de firmware |
| `host/neko_bridge` | Ponte serial Python: JSON Lines, ACK/timeout/retry/dedup, adaptador de backend |
| `app/` | Aplicação web local FastAPI (127.0.0.1: Dashboard, Diagnóstico, Touch Lab, UI Lab, NekoMind) |
| `emulator/` | Emulador do LCD 240×320/320×240 + dispositivo virtual (modo demo) |
| `assets/` | Sprites kawaii originais (PNG + arrays C RGB565 + gerador + licença) |
| `tests/` | Testes Python (pytest) |
| `test/native/` | Testes C++ nativos (Unity via PlatformIO) |
| `scripts/` | Automação PowerShell (build, upload, monitor, testes, app) |
| `docs/` | Protocolo, decisões, riscos, validação física, assets |
| `reports/` | Relatórios de implementação e diagnóstico |
| `storage/` | Dados em runtime (logs, backups de calibração) — não versionado |

## Início rápido (Windows PowerShell)

```powershell
cd C:\Users\mayac\Desktop\high_level_projects\nekomind-touch-platform

# 1. Ambiente Python local (.venv dentro do projeto)
powershell -ExecutionPolicy Bypass -File scripts\install_env.ps1

# 2. Compilar o firmware
powershell -ExecutionPolicy Bypass -File scripts\build.ps1

# 3. Testes automatizados (lógica C++ pura + Python)
powershell -ExecutionPolicy Bypass -File scripts\run_native_tests.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1

# 4. Conectar a placa e gravar
powershell -ExecutionPolicy Bypass -File scripts\detect_ports.ps1
powershell -ExecutionPolicy Bypass -File scripts\upload.ps1     # escolhe a porta com voce
powershell -ExecutionPolicy Bypass -File scripts\monitor.ps1

# 5. Aplicação local (funciona sem hardware, em modo emulador/demo)
powershell -ExecutionPolicy Bypass -File scripts\run_app.ps1
# → http://127.0.0.1:8700
```

## Requisitos de hardware (validados no baseline)

- ESP32-S3-DevKitC-1 (USB CDC, `ARDUINO_USB_CDC_ON_BOOT=1`)
- Display ILI9341 240×320 — MOSI 11, SCK 12, MISO 13, CS 10, DC 9, RST 8, SPI 20 MHz
- Touch XPT2046 — CS 7, IRQ 6 (opcional; leitura forçada com `isrWake=true`)
- Backlight em **3V3** — GPIO48 é o LED RGB da placa e **nunca** deve ser usado
  para backlight

Pinagem completa: `TECHNICAL_REFERENCE.md`. Contrato serial: `docs/protocol.md`.

## Limitações honestas

- Testes automatizados da lógica (calibração, filtros, debounce, protocolo) rodam
  no **host** — não comprovam precisão física do touch.
- A integração com o backend NekoMind usa adaptador + mock; a validação ponta a
  ponta com o backend real está pendente (`docs/risks.md` R10).
- O emulador espelha os comandos de render do firmware — não é validação física.

## Licença de assets

Todos os sprites são gerados pelo próprio projeto
(`assets/generator/generate_assets.py`) — origem e licença em `docs/assets.md`.
Nada é copiado de projetos com licença desconhecida.
