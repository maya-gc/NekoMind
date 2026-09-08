# NekoMind Firmware (ESP32-S3 + ESP-IDF)

Firmware do dispositivo NekoMind: captura a explicação oral do estudante
com um microfone INMP441 (I2S + DMA), mostra o estado da sessão por um
avatar e envia chunks de áudio ao computador via serial USB (JSON Lines).
Wi-Fi é a alternativa planejada de transporte.

## Estados do avatar

`IDLE → RECORDING ⇄ SENDING → PROCESSING → SUCCESS | ERROR`

## O que já funciona (MVP)

- Máquina de estados e orquestração da sessão (`session_controller`).
- Protocolo JSON Lines na serial (ver `docs/iot_protocol.md`).
- Captura e LCD em modo simulado (logs), firmware 100% compilável sem
  hardware.

## TODOs de hardware (preencher antes de gravar na placa)

| Configuração | Arquivo | Descrição |
|---|---|---|
| `NEKO_I2S_PIN_BCLK/WS/DIN` | `main/i2s_microphone.h` | Pinos do INMP441 |
| `NEKO_LCD_PIN_*` | `main/display_ui.h` | Pinos do LCD |
| `NEKO_WIFI_SSID/PASSWORD/HOST/PORT` | `main/audio_transport.h` | Wi-Fi futuro (não versionar valores reais) |
| `NEKO_SAMPLE_RATE_HZ`, `NEKO_AUDIO_CHUNK_SIZE` | headers | Áudio |

## Build

```bash
# Na raiz do repositorio:
source scripts/source_idf.sh
cd iot/nekomind_firmware
idf.py set-target esp32s3
idf.py build
idf.py -p COMx flash monitor   # ajuste a porta
```

## Componentes externos

Coloque drivers adicionais (ex.: LCD) em `components/` — ver
`components/README.md`.
