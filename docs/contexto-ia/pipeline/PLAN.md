# PLAN.md — NekoMind Touch Lab

> Grafo de tarefas da plataforma. Fonte de verdade de execução para os agentes
> (architect → coder → tester → reviewer), conforme o padrão `orquestracao-agents`.
> Este arquivo é atualizado a cada onda de execução. Histórico de iterações: `LOOP_LOG.md`.

## Objetivo

Plataforma local para desenvolver, testar, calibrar, controlar e demonstrar o LCD
ILI9341 240×320 + touch XPT2046 do ESP32-S3 junto ao fluxo NekoMind, com firmware
PlatformIO (driver próprio `ILI9341_Driver`), aplicação local FastAPI, emulador
visual, protocolo serial JSON Lines, testes automatizados e documentação — tudo
dentro desta pasta, sem cartão SD, sem nuvem e semGPIO48 no backlight.

## Contratos obrigatórios (leia antes de codificar)

| Contrato | Arquivo |
|---|---|
| Especificação de hardware, pinagem e decisões críticas | `TECHNICAL_REFERENCE.md` |
| Protocolo serial JSON Lines v2 (superconjunto do NekoMind) | `docs/protocol.md` |
| API C++ pura da lógica (calibração, filtros, debounce, estados, protocolo, layout) | `lib/neko_core/*.h` |
| Configuração de placa (pinos) | `include/BoardConfig.h` |
| Configuração do protocolo (timeouts, limites) | `include/ProtocolConfig.h` |
| Assets kawaii (API dos sprites C) | `assets/c/neko_sprites.h` + `docs/assets.md` |
| Decisões e riscos | `docs/decisions.md`, `docs/risks.md` |

## Regras invariantes

1. Pinagem oficial: MOSI 11, SCK 12, MISO 13, CS display 10, DC 9, RST 8,
   CS touch 7, IRQ touch 6 (opcional). Backlight em 3V3. GPIO48 = só LED RGB.
2. Driver `ILI9341_Driver` próprio (baseline). TFT_eSPI proibido no caminho funcional.
3. SPI global compartilhado, display a 20 MHz, `ts.isrWake = true` antes de ler.
4. Redraw condicional. Sem `delay()` no fluxo interativo. Sem cartão SD. Sem nuvem.
5. Calibração persistida em NVS. Compatibilidade com calibração de 2 pontos.
6. Comentários e documentação em português do Brasil.
7. Sem dados privados em logs; painel público sem transcrição; modo demo identificável.
8. Nada fora de `C:\Users\mayac\Desktop\high_level_projects` (exceto pacotes gerenciados
   pelo PlatformIO em `~/.platformio`, como o toolchain).
9. Simulação nunca é apresentada como validação física.

## Grafo de tarefas

```text
F0 (architect, concluída pela sessão primária)
 ├── F0.1 Árvore de pastas e PLAN.md ──────────────── [OK]
 ├── F0.2 platformio.ini (esp32s3) + test/native (Unity+MinGW) [OK]
 ├── F0.3 include/BoardConfig.h (sem TFT_BL), AppConfig.h, ProtocolConfig.h
 ├── F0.4 docs/protocol.md (contrato v2) + decisions.md + risks.md
 ├── F0.5 lib/neko_core/*.h (contratos C++) + test/native/platformio.ini
 ├── F0.6 Cópia do baseline → lib/neko_display + firmware/baseline + proveniência
 └── F0.7 requirements.txt, conftest.py, scripts/*.ps1, .vscode, .gitignore, README

Onda 1 (paralela, arquivos disjuntos)
 ├── T1A coder → lib/neko_core/*.cpp + test/native/test_neko_core.cpp
 ├── T1C coder → host/neko_bridge + app/ (FastAPI + HTML/JS) + tests/ (pytest)
 └── T1E coder → assets/ (gerador + PNG + arrays C + licença)
     dependências: T1A/T1C dependem de F0.*; T1E depende de F0.1

Onda 2 (após T1A + T1E)
 ├── T2B coder → src/ (main, SerialProtocol, SessionController, UiManager,
 │            Diagnostics) + lib/neko_touch/TouchManager + renderer LCD
 │            dependências: T1A (neko_core .cpp), T1E (sprites C), F0.6 (drivers)
 └── T3D coder → emulator/ + integração na aba do app
              dependências: T1C (app), docs/protocol.md

Onda 3
 ├── T4  tester → pio run + pio test (native) + pytest; ciclo de correções
 │            dependências: T2B, T3D
 └── T5  reviewer → conformidade com as regras invariantes + revisão de código
              dependências: T4

Onda 4 (encerramento)
 └── T6  primária → reports/implementation-report.md, verificação da árvore,
                   atualização de TECHNICAL_REFERENCE.md, LOOP_LOG final
```

## Critérios de aceite por tarefa

| Tarefa | Critério |
|---|---|
| T1A | `scripts/run_native_tests.ps1` passa: calibração 2/4 pts, mapeamento, filtros EMA/média móvel, debounce/histerese, press/move/release, hit-test de botões, rotação, máquina de estados, parser JSON Lines, dedup, rejeição de sessão antiga, layout 240×320/320×240, overflow, limite de termos, persistência (mock de NVS) |
| T1C | `scripts/run_tests.ps1` passa: parser/codec JSON Lines em Python, ponte serial com ACK/timeout/retry/dedup, adaptador backend (mock) + NekoMind (HTTP), endpoints FastAPI em 127.0.0.1, modo demo identificável, relatórios |
| T1E | `assets/png/*.png` + `assets/c/neko_sprites.h` gerados por `assets/generator/generate_assets.py`; licença e origem em `docs/assets.md`; sprites 48×48 |
| T2B | `scripts/build.ps1` compila o firmware completo (main + UI kawaii + protocolo + touch) |
| T3D | Emulador renderiza telas 240×320 e 320×240 a partir de comandos `screen_update` e do dispositivo virtual; rotulado como simulação |
| T4 | Todos os testes verdes: firmware compila, native pass, pytest pass |
| T5 | Revisão sem violações de regra invariante; pendências documentadas |
| T6 | `reports/implementation-report.md` separando: confirmado por código / por teste automatizado / observado em simulação / pendente de validação física |

## Execução

- Onda 1: T1A, T1C e T1E em paralelo (diretórios disjuntos).
- Onda 2: T2B e T3D em paralelo (T2B após T1A+T1E; T3D após T1C).
- Onda 3: T4 (tester) e depois T5 (reviewer) com correções conforme necessário.
- Onda 4: T6 pela sessão primária.
