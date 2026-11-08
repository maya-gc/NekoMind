# [NekoMind Touch Lab] Capa de atualizacao

> **Este documento e a referencia tecnica OFICIAL do NekoMind Touch Lab.**
> Ele foi herdado integralmente do projeto baseline esp32_lcd_test (19/09/2026)
> e e a fonte primaria de decisoes de hardware e integracao.
>
> Atualizacoes especificas do Touch Lab:
> - docs/decisions.md — decisoes D01..D15 (inclui a remocao do define TFT_BL 48, ausente deste snapshot original)
> - docs/risks.md — riscos R01..R11 e checklist de validacao fisica
> - docs/protocol.md — contrato serial JSON Lines v2
>
> O conteudo a seguir e o documento baseline, preservado sem alteracoes.

---
# ReferÃªncia TÃ©cnica â€” ESP32-S3 + LCD ILI9341 + Touch XPT2046

> **Documento de memÃ³ria tÃ©cnica permanente.** Projetado para ser consumido tanto por humanos quanto por novas sessÃµes de IA, preservando todas as decisÃµes, configuraÃ§Ãµes, pinagens, drivers e conhecimento acumulado deste projeto.
>
> **Como usar este documento (para IA):** antes de qualquer modificaÃ§Ã£o no projeto, leia as seÃ§Ãµes [1 (Hardware)](#1-documentaÃ§Ã£o-do-hardware), [2 (Pinagem)](#2-mapa-oficial-de-pinagem-do-projeto), [3 (Drivers)](#3-drivers-e-bibliotecas), [6 (DecisÃµes)](#6-decisÃµes-tÃ©cnicas-e-conhecimento-acumulado) e [7 (CrÃ­ticos)](#7-componentes-e-configuraÃ§Ãµes-crÃ­ticas--nÃ£o-alterar-sem-justificativa). NÃ£o altere nada marcado como crÃ­tico sem justificativa documentada.
>
> **Idioma:** PortuguÃªs do Brasil. **Estado:** Projeto em desenvolvimento ativo.

---

## Ãndice

- [VisÃ£o geral](#visÃ£o-geral)
- [1. DocumentaÃ§Ã£o do hardware](#1-documentaÃ§Ã£o-do-hardware)
- [2. Mapa oficial de pinagem do projeto](#2-mapa-oficial-de-pinagem-do-projeto)
- [3. Drivers e bibliotecas](#3-drivers-e-bibliotecas)
- [4. ConfiguraÃ§Ã£o do ambiente](#4-configuraÃ§Ã£o-do-ambiente)
- [5. Arquitetura do software](#5-arquitetura-do-software)
- [6. DecisÃµes tÃ©cnicas e conhecimento acumulado](#6-decisÃµes-tÃ©cnicas-e-conhecimento-acumulado)
- [7. Componentes e configuraÃ§Ãµes crÃ­ticas â€” NÃƒO ALTERAR sem justificativa](#7-componentes-e-configuraÃ§Ãµes-crÃ­ticas--nÃ£o-alterar-sem-justificativa)
- [8. Problemas, erros e soluÃ§Ãµes](#8-problemas-erros-e-soluÃ§Ãµes)
- [9. ReproduÃ§Ã£o do projeto do zero](#9-reproduÃ§Ã£o-do-projeto-do-zero)
- [10. Checklist de validaÃ§Ã£o](#10-checklist-de-validaÃ§Ã£o)
- [11. PadrÃ£o base para projetos ESP32 + LCD](#11-padrÃ£o-base-para-projetos-esp32--lcd)
- [12. Compatibilidade e reutilizaÃ§Ã£o](#12-compatibilidade-e-reutilizaÃ§Ã£o)
- [13. Estado atual do projeto](#13-estado-atual-do-projeto)
- [14. Formato final](#14-formato-final)

---

## VisÃ£o geral

O projeto `esp32_lcd_test` Ã© um **ambiente de teste embarcado** para o **ESP32-S3** com um **display TFT 2,4" 240Ã—320 ILI9341** e **touch resistivo XPT2046**. Seu objetivo Ã© permitir testar rapidamente o hardware (placa, USB, SPI, display, touch), exibir estados na tela e no serial, e servir de base para novos projetos ESP32 + LCD.

**Resultado atual alcanÃ§ado:**
- LCD ILI9341 funcionando via driver SPI de baixo nÃ­vel prÃ³prio (sem TFT_eSPI).
- Texto 5Ã—7 legÃ­vel no display (fonte Adafruit clÃ¡ssica, Ã­ndice `c*5`).
- Touch XPT2046 detectado e calibraÃ§Ã£o por 2 pontos implementada (funcionando, ainda nÃ£o perfeito).
- Dashboard e navegaÃ§Ã£o por estados no LCD.
- Comandos serial para navegaÃ§Ã£o (Ãºtil quando o touch ainda nÃ£o estÃ¡ calibrado).
- Interface estÃ¡vel (redraw condicional, sem flicker).

**DecisÃ£o central:** o driver `TFT_eSPI` foi **testado e descartado** porque travava no `tft.begin()` neste hardware. Foi substituÃ­do por um driver ILI9341 SPI de baixo nÃ­vel escrito no prÃ³prio projeto. Esta Ã© a decisÃ£o mais importante deste projeto.

---

## 1. DocumentaÃ§Ã£o do hardware

### 1.1 Placa / MCU

| Item | Valor | Status |
|------|-------|--------|
| **Placa** | Espressif ESP32-S3-DevKitC-1 | confirmado por esptool |
| **MCU** | ESP32-S3 (QFN56), revisÃ£o v0.2 | confirmado por esptool |
| **FrequÃªncia CPU** | 240 MHz | padrÃ£o do board |
| **RAM** | 320 KB (SRAM) | confirmado no build |
| **Flash (board)** | 8 MB QD | definiÃ§Ã£o do board `esp32-s3-devkitc-1` |
| **Flash (detectado)** | 16 MB | **NECESSITA VALIDAÃ‡ÃƒO** â€” esptool reportou 16MB, mas o board define 8MB |
| **PSRAM (detectado)** | 8 MB embutida (AP_3v3) | **NECESSITA VALIDAÃ‡ÃƒO** â€” esptool reportou PSRAM, mas o board define "No PSRAM" |
| **USB mode** | USB-Serial/JTAG | confirmado |
| **MAC** | `d8:3b:da:43:19:90` | confirmado |

> **âš ï¸ NECESSITA VALIDAÃ‡ÃƒO:** o esptool reportou flash de 16MB e PSRAM 8MB embutida, mas o board PlatformIO `esp32-s3-devkitc-1` define 8MB QD sem PSRAM. Isso sugere que o mÃ³dulo fÃ­sico pode ser um **ESP32-S3-WROOM-1 N16R8** (ou similar). A confirmaÃ§Ã£o exata do mÃ³dulo nÃ£o foi feita. Se o PSRAM for real, pode ser habilitado via build_flags `-DBOARD_HAS_PSRAM` e ajuste de partiÃ§Ãµes â€” **mas nÃ£o foi testado**.

### 1.2 PerifÃ©ricos externos

| PerifÃ©rico | Fabricante | Modelo | Controlador | ComunicaÃ§Ã£o | AlimentaÃ§Ã£o |
|------------|------------|--------|-------------|-------------|-------------|
| **Display TFT** | genÃ©rico (mÃ³dulo 2,4") | TFT 2,4" 240Ã—320 | **ILI9341** | SPI (4 fios + CS/DC/RST) | 3V3 |
| **Touch** | genÃ©rico (integrado ao mÃ³dulo) | painel resistivo | **XPT2046** | SPI (compartilhado com display) | 3V3 |
| **LED RGB** | Espressif (na placa) | WS2812 | WS2812 | 1-wire (neopixel) | 3V3 |
| **Backlight** | â€” | LED backlight | â€” | GPIO ou 3V3 | 3V3 |

> **Importante:** o GPIO48 Ã© o **LED RGB WS2812 da prÃ³pria placa** (Neopixel). O backlight do display **nÃ£o deve** ser conectado ao GPIO48 â€” se for, conflita com o LED RGB. **A soluÃ§Ã£o atual usa o backlight em 3V3** (sempre aceso).

### 1.3 Interfaces utilizadas

| Interface | Uso | ObservaÃ§Ãµes |
|-----------|-----|-------------|
| **SPI (FSPI/SPI2)** | Display + touch compartilham o mesmo barramento | MOSI=11, MISO=13, SCK=12 |
| **GPIO** | CS/DC/RST do display, CS do touch, IRQ do touch | ver pinagem |
| **USB-Serial/JTAG** | Upload + serial (COM3) | `ARDUINO_USB_CDC_ON_BOOT=1` |
| **NVS (Preferences)** | Armazenar calibraÃ§Ã£o do touch | namespace `touch` |

### 1.4 TensÃµes e nÃ­veis lÃ³gicos

- AlimentaÃ§Ã£o: **3V3** (display, touch, LED RGB).
- NÃ­veis lÃ³gicos: **3.3V** (todos os GPIOs do ESP32-S3).
- O ILI9341 e o XPT2046 sÃ£o alimentados a 3.3V e operam com lÃ³gica 3.3V.
- Backlight: 3V3 (ou PWM em um GPIO livre â€” nÃ£o usar GPIO48).

### 1.5 Particularidades elÃ©tricas e limitaÃ§Ãµes conhecidas

- **GPIO48 Ã© o LED RGB da placa** (WS2812). NÃ£o usar para backlight.
- **IRQ do touch (GPIO6)** nÃ£o dispara de forma confiÃ¡vel; o firmware forÃ§a a leitura (`ts.isrWake = true`).
- **Flash/PSRAM:** a detecÃ§Ã£o do esptool sugere 16MB/8MB PSRAM, mas isso nÃ£o foi validado no firmware. **NÃƒO CONFIRMADO.**
- O touch e o display compartilham o barramento SPI â€” Ã© obrigatÃ³rio usar **transaÃ§Ãµes SPI** (`beginTransaction`/`endTransaction`) para evitar colisÃµes.
- Ao abrir a porta serial com pyserial e resetar o chip, o ESP32-S3 **entra em modo download** (`boot:0x0 DOWNLOAD`). Para rodar o app, pressione **RST** com a porta fechada.

---

## 2. Mapa oficial de pinagem do projeto

> **Esta Ã© a pinagem baseline oficial.** Qualquer alteraÃ§Ã£o deve ser justificada e documentada. Os pinos estÃ£o definidos em `include/BoardConfig.h`.

### 2.1 Tabela consolidada

| GPIO | FunÃ§Ã£o | Componente | Interface | DireÃ§Ã£o | ObrigatÃ³rio | ObservaÃ§Ãµes |
|------|--------|------------|-----------|---------|-------------|-------------|
| **GPIO11** | MOSI (SDI) | display + touch | SPI | Out | Sim | Compartilhado display/touch |
| **GPIO12** | SCK/CLK | display + touch | SPI | Out | Sim | Compartilhado display/touch |
| **GPIO13** | MISO (SDO) | display + touch | SPI | In | Sim | Compartilhado display/touch |
| **GPIO10** | CS display | ILI9341 | SPI | Out | Sim | Ativo baixo |
| **GPIO9** | DC/RS | ILI9341 | GPIO | Out | Sim | Data=1, Command=0 |
| **GPIO8** | RST/RESET | ILI9341 | GPIO | Out | Sim | Reset ativo baixo |
| **GPIO7** | CS touch | XPT2046 | SPI | Out | Sim | Ativo baixo |
| **GPIO6** | IRQ touch | XPT2046 | GPIO In (pull-up) | In | Opcional | NÃ£o Ã© usado de forma confiÃ¡vel |
| **GPIO48** | LED RGB | WS2812 (placa) | Neopixel | Out | NÃ£o | **NÃƒO usar como backlight** |
| **GPIO43/44** | TX/RX UART0 | â€” | UART | â€” | NÃ£o | NÃ£o usados no firmware |

### 2.2 Detalhamento por pino

| GPIO | FunÃ§Ã£o | Detalhes |
|------|--------|----------|
| **GPIO11 (MOSI)** | Dado SPI para display e touch | DireÃ§Ã£o: saÃ­da. Estado esperado: alto quando inativo. Pull: nenhum (SPI). Conflitos: compartilhado com touch. Motivo: pino padrÃ£o FSPI MOSI do ESP32-S3 (variante esp32s3: MOSI=11). |
| **GPIO12 (SCK)** | Clock SPI | DireÃ§Ã£o: saÃ­da. Estado esperado: clock. Conflitos: compartilhado com touch. Motivo: pino padrÃ£o FSPI SCK (variante esp32s3: SCK=12). |
| **GPIO13 (MISO)** | Retorno de dados do display/touch | DireÃ§Ã£o: entrada. Conflitos: compartilhado com touch. Motivo: pino padrÃ£o FSPI MISO (variante esp32s3: MISO=13). |
| **GPIO10 (CS display)** | Chip select do ILI9341 | DireÃ§Ã£o: saÃ­da. Ativo baixo. Conflitos: nenhum. Motivo: pino padrÃ£o SS da variante esp32s3 (SS=10). ObrigatÃ³rio. |
| **GPIO9 (DC)** | Data/Command do ILI9341 | DireÃ§Ã£o: saÃ­da. Estado: HIGH = dado, LOW = comando. Motivo: DC do mÃ³dulo. ObrigatÃ³rio. |
| **GPIO8 (RST)** | Reset do ILI9341 | DireÃ§Ã£o: saÃ­da. Ativo baixo. ObrigatÃ³rio. |
| **GPIO7 (CS touch)** | Chip select do XPT2046 | DireÃ§Ã£o: saÃ­da. Ativo baixo. ObrigatÃ³rio. |
| **GPIO6 (IRQ touch)** | InterrupÃ§Ã£o de toque | DireÃ§Ã£o: entrada com pull-up. Opcional â€” o firmware forÃ§a `isrWake=true`, entÃ£o a IRQ nÃ£o Ã© essencial. |
| **GPIO48 (LED RGB)** | WS2812 da placa | DireÃ§Ã£o: saÃ­da. **NÃƒO usar como backlight.** |

### 2.3 Notas de pinagem

- Os pinos SPI (11/12/13) coincidem com os pinos padrÃ£o FSPI da variante `esp32s3` (`pins_arduino.h`: MOSI=11, MISO=13, SCK=12, SS=10). Isso Ã© intencional: facilita o uso do `SPI` global do Arduino.
- **Conflitos conhecidos:** GPIO48 Ã© o LED RGB; GPIO43/44 sÃ£o UART0 (nÃ£o usados).
- **GPIOs nÃ£o utilizados (relevantes):** GPIO43 (TX), GPIO44 (RX), GPIO48 (LED RGB). Outros GPIOs livres: 1-5, 14-18, 20, 21, 33-42, 45-47 (a verificar se hÃ¡ conflito com PSRAM/Flash â€” **NECESSITA VALIDAÃ‡ÃƒO**).

---

## 3. Drivers e bibliotecas

### 3.1 Resumo de classificaÃ§Ã£o

| Componente | VersÃ£o | ClassificaÃ§Ã£o | Status |
|------------|--------|---------------|--------|
| **ILI9341_Driver** (prÃ³prio) | â€” | Utilizado | Driver SPI bruto do display |
| **XPT2046_Touchscreen** | `0.0.0-alpha+sha.26b691b2c8` | Utilizado | Biblioteca do touch |
| **ArduinoLog** | `1.1.1` (thijse) | Utilizado | Log estruturado |
| **Font5x7.h** (cÃ³pia) | clÃ¡ssica Adafruit | Utilizado | Fonte 5Ã—7 |
| **TFT_eSPI** | `2.5.0` | **Testado e descartado** | Travava no `tft.begin()` |
| **Adafruit GFX Library** | `1.12.6` | Instalado, nÃ£o utilizado | â€” |
| **Arduino-ESP32 core** | `2.0.17` | Requerido | Framework |
| **PlatformIO** | `6.2.0` | Requerido (dev) | Ferramenta |
| **Plataforma espressif32** | `7.1.3` | Requerido (dev) | Plataforma |
| **Adafruit BusIO** | `1.17.4` | Instalado, nÃ£o utilizado | â€” |
| **ArduinoJson** | `7.4.3` | Instalado, nÃ£o utilizado | â€” |

### 3.2 Drivers e bibliotecas detalhados

#### 3.2.1 ILI9341_Driver (driver prÃ³prio) â€” UTILIZADO
- **Nome:** `ILI9341_Driver` (em `include/ILI9341_Driver.h` e `src/ILI9341_Driver.cpp`).
- **Origem:** escrito para este projeto (nÃ£o Ã© biblioteca externa).
- **FunÃ§Ã£o:** driver de baixo nÃ­vel do display ILI9341 via SPI bruto. Implementa: `begin`, `setRotation`, `fillScreen`, `fillRect`, `drawRect`, `drawCircle`, `fillCircle`, `drawLine`, `drawPixel`, texto 5Ã—7 (`print`, `printNum`, `setTextColor`, `setCursor`).
- **Hardware que controla:** ILI9341 (display 240Ã—320).
- **ConfiguraÃ§Ã£o:** pinos em `BoardConfig.h`, frequÃªncia em `AppConfig.h` (`SPI_DISPLAY_FREQ = 20000000UL`).
- **Como foi configurado:** usa o objeto `SPI` global do Arduino (`_spi = &SPI;`), `SPI.begin(TFT_SCLK, TFT_MISO, TFT_MOSI, TFT_CS)`. SequÃªncia de init: SWRESET, SLPOUT, MADCTL (0x48), COLMOD 16bit (0x55), Display Function, Power Control, DISPON.
- **DependÃªncias:** Arduino core, `SPI.h`, `BoardConfig.h`, `AppConfig.h`, `Font5x7.h`.
- **Motivo da escolha:** TFT_eSPI travava no hardware; driver prÃ³prio funciona de forma confiÃ¡vel.
- **Alternativas consideradas:** TFT_eSPI (descartado), Adafruit_ILI9341 (nÃ£o testado).
- **Problemas encontrados:** fonte com letras trocadas (Ã­ndice `c*5` nÃ£o `(c-32)*5`).
- **LimitaÃ§Ãµes:** texto em fonte fixa 5Ã—7; sem suporte a fontes vetoriais; sem DMA.
- **ObrigatÃ³rio:** sim. **Pode ser substituÃ­do:** sim (por outro driver), com revalidaÃ§Ã£o.
- **Reinstalar em nova mÃ¡quina:** o cÃ³digo estÃ¡ no projeto; nÃ£o requer instalaÃ§Ã£o externa.

#### 3.2.2 XPT2046_Touchscreen â€” UTILIZADO
- **Nome:** `XPT2046_Touchscreen` (PaulStoffregen).
- **VersÃ£o:** `0.0.0-alpha+sha.26b691b2c8` (a Ãºnica disponÃ­vel no registro PlatformIO).
- **Origem:** https://github.com/PaulStoffregen/XPT2046_Touchscreen (via registro PlatformIO).
- **FunÃ§Ã£o:** leitura do touch resistivo XPT2046.
- **ConfiguraÃ§Ã£o:** `lib_deps = paulstoffregen/XPT2046_Touchscreen@0.0.0-alpha+sha.26b691b2c8`. Instanciada em `TouchManager` com `ts(TOUCH_CS, TOUCH_IRQ)`.
- **Como foi configurada:** `SPI.begin(TFT_SCLK, TFT_MISO, TFT_MOSI, TFT_CS)` antes de `ts.begin()`. `ts.setRotation(1)`. Uso do `ts.isrWake = true` para forÃ§ar leitura (crÃ­tico â€” ver seÃ§Ã£o 6/7).
- **DependÃªncias:** `SPI.h`, Arduino core.
- **Problemas encontrados:** a IRQ (GPIO6) nÃ£o dispara de forma confiÃ¡vel; a biblioteca sÃ³ lia se `isrWake=true`. As coordenadas brutas retornadas pela biblioteca precisam de calibraÃ§Ã£o (mapping para tela).
- **LimitaÃ§Ãµes:** versÃ£o alpha; suporte a ISR frÃ¡gil; calibraÃ§Ã£o precisa ser feita externamente.
- **ObrigatÃ³rio:** sim (para o touch). **Pode ser substituÃ­do:** sim (outra lib de touch).
- **Reinstalar:** `pio pkg install "paulstoffregen/XPT2046_Touchscreen@0.0.0-alpha+sha.26b691b2c8"` ou automÃ¡tico pelo `lib_deps`.

#### 3.2.3 ArduinoLog â€” UTILIZADO
- **Nome:** `ArduinoLog` (Thijs Elenbaas).
- **VersÃ£o:** `1.1.1`.
- **Origem:** https://github.com/thijse/Arduino-Log (registro PlatformIO).
- **FunÃ§Ã£o:** log estruturado com nÃ­veis (ERROR, WARN, INFO, DEBUG/VERBOSE, TRACE).
- **ConfiguraÃ§Ã£o:** `lib_deps = thijse/ArduinoLog@1.1.1`. Inicializado em `main.cpp`: `Log.begin(LOG_LEVEL_INFO, &Serial)`.
- **DependÃªncias:** Arduino core.
- **Problemas encontrados:** ambÃ­guo com outros pacotes; `LOG_LEVEL_DEBUG` nÃ£o existe na versÃ£o â€” usar `LOG_LEVEL_VERBOSE`.
- **ObrigatÃ³rio:** sim (usado em vÃ¡rios mÃ³dulos). **SubstituÃ­vel:** sim.

#### 3.2.4 Font5x7.h (cÃ³pia da fonte Adafruit) â€” UTILIZADO
- **Nome:** fonte clÃ¡ssica 5Ã—7 do Adafruit GFX.
- **Origem:** copiada de `Adafruit GFX Library` (`glcdfont.c`) para `include/Font5x7.h`.
- **FunÃ§Ã£o:** fonte bitmap 5Ã—7 para o driver ILI9341.
- **ConfiguraÃ§Ã£o:** `#include "Font5x7.h"` no `ILI9341_Driver.cpp`.
- **DependÃªncias:** nenhuma.
- **Problemas encontrados:** **o Ã­ndice correto Ã© `c*5` (nÃ£o `(c-32)*5`)** â€” usar `(c-32)*5` fazia letras aparecerem como sÃ­mbolos/nÃºmeros.
- **ObrigatÃ³rio:** sim (para o texto). **SubstituÃ­vel:** sim (outra fonte).

#### 3.2.5 TFT_eSPI â€” TESTADO E DESCARTADO
- **Nome:** `TFT_eSPI` (Bodmer).
- **VersÃ£o:** `2.5.0`.
- **Origem:** https://github.com/Bodmer/TFT_eSPI (registro PlatformIO).
- **FunÃ§Ã£o:** biblioteca grÃ¡fica para TFTs (ILI9341, ST7789, etc.).
- **Motivo do descarte:** **travava (crash/loop de reset) em `tft.begin()`** neste hardware especÃ­fico (ESP32-S3 + pino 48). O LED RGB ficava parado em magenta (dentro de `tft.begin()`), indicando travamento.
- **CircunstÃ¢ncias para uso futuro:** se a causa do travamento for identificada (possÃ­vel conflito de pinos ou versÃ£o), poderia ser usada. **Alternativa adotada:** driver SPI bruto prÃ³prio.
- **Como reinstalar (se reavaliar):** `lib_deps = bodmer/TFT_eSPI@2.5.0` e configurar via `User_Setup.h` ou build_flags.

#### 3.2.6 Adafruit GFX Library / BusIO / ArduinoJson â€” INSTALADO, NÃƒO UTILIZADO
- Presentes em `.pio/libdeps` (por dependÃªncias anteriores ou tentativas), mas **nÃ£o sÃ£o usados no cÃ³digo atual**. A fonte 5Ã—7 foi copiada manualmente para o projeto. Podem ser removidos do `lib_deps` (jÃ¡ nÃ£o estÃ£o em `platformio.ini`).

---

## 4. ConfiguraÃ§Ã£o do ambiente

### 4.1 Ferramentas e versÃµes

| Ferramenta | VersÃ£o | ObservaÃ§Ãµes |
|------------|--------|-------------|
| **Sistema operacional** | Windows (PowerShell 5.1) | caminhos com `\` |
| **IDE** | VS Code + extensÃ£o PlatformIO | â€” |
| **PlatformIO Core** | `6.2.0` | instalado via `pip --user` |
| **Plataforma** | `espressif32@7.1.3` | gerida pelo PlatformIO |
| **Framework** | Arduino-ESP32 `2.0.17` | framework-arduinoespressif32 |
| **Compiler** | toolchain-xtensa-esp32s3 (8.4.0+2021r2-patch5) | gerenciado pelo PlatformIO |
| **esptool** | `tool-esptoolpy 2.41100.260830` | upload |
| **Python** | 3.13 | para `pio` e scripts |
| **pio.exe** | `C:\Users\mayac\AppData\Roaming\Python\Python313\Scripts\pio.exe` | **nÃ£o estÃ¡ no PATH** â€” usar caminho completo |

### 4.2 Caminho do `pio.exe`

O `pio` **nÃ£o estÃ¡ no PATH**. Use o caminho completo ou adicione ao PATH:

```powershell
C:\Users\mayac\AppData\Roaming\Python\Python313\Scripts\pio.exe run
```

### 4.3 Arquivo `platformio.ini` (atual)

```ini
[env:esp32s3]
platform = espressif32
board = esp32-s3-devkitc-1
framework = arduino
monitor_speed = 115200
upload_speed = 921600
build_flags =
	-D ARDUINO_USB_CDC_ON_BOOT=1
lib_deps =
	thijse/ArduinoLog@1.1.1
	paulstoffregen/XPT2046_Touchscreen@0.0.0-alpha+sha.26b691b2c8

[env:esp32s3_debug]
extends = env:esp32s3
build_type = debug
```

**ObservaÃ§Ãµes de build:**
- `monitor_speed = 115200` (baud do monitor serial).
- `upload_speed = 921600`.
- `ARDUINO_USB_CDC_ON_BOOT=1`: habilita USB CDC no boot (Serial via USB).
- **PartiÃ§Ãµes:** padrÃ£o `default_8MB.csv` (definiÃ§Ã£o do board). `NECESSITA VALIDAÃ‡ÃƒO` se a flash real for 16MB.
- **MemÃ³ria:** o build atual usa ~6,1% de RAM (â‰ˆ19.8 KB) e ~8,5% de Flash (â‰ˆ283 KB).

### 4.4 Scripts auxiliares

| Script | FunÃ§Ã£o |
|--------|--------|
| `scripts/detect_esp32_ports.ps1` | Lista portas COM via `Get-CimInstance Win32_PnPEntity` |
| `scripts/diagnose_esp32.ps1` | Verifica Python, pio, esptool, arquivos do projeto |
| `scripts/upload_and_monitor.ps1` | Compila, pede confirmaÃ§Ã£o, faz upload, abre monitor |
| `scripts/probe_display.py` | Pipeline Python de iteraÃ§Ã£o de drivers (usada para diagnosticar o display) |

### 4.5 Tarefas do VS Code (`.vscode/tasks.json`)

- **Build**: `pio run`
- **Upload**: `pio run -t upload`
- **Monitor**: `pio device monitor`
- **DiagnÃ³stico**: `powershell -ExecutionPolicy Bypass -File scripts\diagnose_esp32.ps1`
- **Limpar**: `pio run -t clean`

---

## 5. Arquitetura do software

### 5.1 Estrutura de diretÃ³rios

```
esp32_lcd_test/
â”œâ”€â”€ platformio.ini
â”œâ”€â”€ README.md
â”œâ”€â”€ TECHNICAL_REFERENCE.md        (este documento)
â”œâ”€â”€ include/
â”‚   â”œâ”€â”€ AppConfig.h               (configuraÃ§Ãµes gerais)
â”‚   â”œâ”€â”€ BoardConfig.h             (pinagem)
â”‚   â”œâ”€â”€ DisplayManager.h          (API de alto nÃ­vel do display)
â”‚   â”œâ”€â”€ TouchManager.h            (API de alto nÃ­vel do touch)
â”‚   â”œâ”€â”€ Diagnostics.h             (testes de diagnÃ³stico)
â”‚   â”œâ”€â”€ TestRunner.h              (registro/execuÃ§Ã£o de testes)
â”‚   â”œâ”€â”€ UiManager.h               (UI, mÃ¡quina de estados)
â”‚   â”œâ”€â”€ ILI9341_Driver.h          (driver bruto do display)
â”‚   â””â”€â”€ Font5x7.h                 (fonte 5Ã—7 Adafruit)
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ main.cpp                  (setup, loop, comandos serial)
â”‚   â”œâ”€â”€ DisplayManager.cpp
â”‚   â”œâ”€â”€ TouchManager.cpp
â”‚   â”œâ”€â”€ Diagnostics.cpp
â”‚   â”œâ”€â”€ TestRunner.cpp
â”‚   â”œâ”€â”€ UiManager.cpp
â”‚   â””â”€â”€ ILI9341_Driver.cpp
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ detect_esp32_ports.ps1
â”‚   â”œâ”€â”€ diagnose_esp32.ps1
â”‚   â”œâ”€â”€ upload_and_monitor.ps1
â”‚   â””â”€â”€ probe_display.py
â””â”€â”€ .vscode/
    â”œâ”€â”€ settings.json
    â””â”€â”€ tasks.json
```

### 5.2 Responsabilidade de cada mÃ³dulo

| MÃ³dulo | Responsabilidade |
|--------|------------------|
| `AppConfig.h` | Constantes globais (baud, frequÃªncias SPI, timeouts, versÃ£o). |
| `BoardConfig.h` | DefiniÃ§Ãµes de pinos (baseline oficial). |
| `ILI9341_Driver` | Driver SPI de baixo nÃ­vel do display: init, primitivas, texto. |
| `DisplayManager` | Wrapper de alto nÃ­vel do display: dashboard, status, texto, formas. |
| `TouchManager` | Wrapper do touch: init, leitura, calibraÃ§Ã£o 2 pontos, NVS. |
| `Diagnostics` | Pipeline de diagnÃ³stico (chip, GPIO, USB, SPI, display, touch, memÃ³ria, FS). |
| `TestRunner` | Registro e execuÃ§Ã£o de testes (atualmente parcial). |
| `UiManager` | MÃ¡quina de estados da UI, navegaÃ§Ã£o, telas. |
| `main.cpp` | InicializaÃ§Ã£o, loop, comandos serial. |

### 5.3 Fluxo de execuÃ§Ã£o

```
setup()
 â”œâ”€ Serial.begin(115200) + aguarda atÃ© 2s
 â”œâ”€ Log.begin(LOG_LEVEL_INFO, &Serial)
 â”œâ”€ gDisplay.begin()   â†’ ILI9341_Driver::begin() (SPI + init display)
 â”œâ”€ gTouch.begin()     â†’ SPI.begin + ts.begin() + loadCalibration()
 â”œâ”€ gUi.begin()        â†’ se touch nÃ£o calibrado, abre STATE_TOUCH_TEST
 â””â”€ gTestRunner.registerTests()

loop()
 â”œâ”€ gUi.update()
 â”‚   â”œâ”€ lÃª touch (getTouch / getTouchRaw)
 â”‚   â”œâ”€ detecÃ§Ã£o de borda (tocar/soltar)
 â”‚   â”œâ”€ timeout (30s) â†’ volta ao dashboard
 â”‚   â””â”€ redraw condicional (_needRedraw)
 â””â”€ lÃª comandos serial â†’ navegaÃ§Ã£o / log
```

### 5.4 MÃ¡quina de estados da UI

```
STATE_DASHBOARD â”€â”€â”€> STATE_DIAGNOSTIC
      â”‚                 STATE_DISPLAY_TEST
      â”‚                 STATE_TOUCH_TEST (calibraÃ§Ã£o 2 pontos)
      â”‚                 STATE_CALIBRATION
      â”‚                 STATE_INFO
      â”‚                 STATE_SETTINGS
      â”‚                 STATE_LOG
      â””â”€â”€ timeout (30s) volta ao dashboard
```

- A transiÃ§Ã£o ocorre por **toque na barra inferior** ou **comando serial** (`touch`, `diag`, `display`, `calibrate`, `home`).
- O **redraw Ã© condicional** (`_needRedraw`), evitando flicker.

### 5.4 ComunicaÃ§Ã£o SPI compartilhada

Display e touch compartilham o mesmo barramento FSPI (SPI2):

```
ESP32-S3 (FSPI)
 â”œâ”€â”€ MOSI (11) â†’ display + touch
 â”œâ”€â”€ SCK  (12) â†’ display + touch
 â”œâ”€â”€ MISO (13) â† display + touch
 â”œâ”€â”€ CS display (10)
 â””â”€â”€ CS touch (7)
```

**Regra crÃ­tica:** toda comunicaÃ§Ã£o SPI deve usar `SPI.beginTransaction(...)`/`SPI.endTransaction(...)` para serializar o acesso. O driver ILI9341 e a biblioteca XPT2046 usam transaÃ§Ãµes, por isso compartilham o barramento sem colisÃ£o.

### 5.6 InicializaÃ§Ã£o de perifÃ©ricos

1. **Display:** `ILI9341Driver::begin()` â€” configura pinos, `SPI.begin(12,13,11,10)`, reset (RST), sequÃªncia de init, `setRotation(0)`.
2. **Touch:** `TouchManager::begin()` â€” `SPI.begin(...)` (mesmos pinos), `ts.begin()`, `ts.setRotation(1)`, `loadCalibration()` (NVS).

### 5.7 Tratamento de erros

- `gDisplay.begin()`/`gTouch.begin()` retornam bool; falha Ã© logada via `Log.error`.
- `Diagnostics::runFull()` executa uma pipeline de testes, cada um com `DiagnosticResult` (PASS/FAIL/WARN/SKIP).
- O `UiManager` usa `Log.notice` para eventos de navegaÃ§Ã£o.

### 5.8 Gerenciamento de memÃ³ria

- Objetos globais Ãºnicos (`gDisplay`, `gTouch`, `gDiagnostics`, `gUi`, `gTestRunner`).
- `ILI9341Driver` aloca `SPIClass` apontando para o `SPI` global (`_spi = &SPI`) â€” sem alocaÃ§Ã£o extra.
- CalibraÃ§Ã£o do touch persistida em NVS (Preferences).

---

## 6. DecisÃµes tÃ©cnicas e conhecimento acumulado

> **Objetivo:** evitar que uma nova IA repita erros jÃ¡ solucionados. Cada decisÃ£o tem o "o que nÃ£o deve ser alterado sem reavaliaÃ§Ã£o".

### D1. Substituir TFT_eSPI por driver ILI9341 prÃ³prio
- **Problema:** TFT_eSPI 2.5.0 travava em `tft.begin()` (LED RGB parado em magenta = loop de reset / travamento).
- **Alternativas:** TFT_eSPI (descartado), driver bruto prÃ³prio (escolhido), Adafruit_ILI9341 (nÃ£o testado).
- **SoluÃ§Ã£o:** escrever `ILI9341_Driver` usando SPI bruto.
- **Motivo:** TFT_eSPI nÃ£o funcionava neste hardware; driver prÃ³prio Ã© confiÃ¡vel e sem dependÃªncias externas.
- **ConsequÃªncias:** sem fontes vetoriais/DMA; texto 5Ã—7; mais cÃ³digo mantido manualmente.
- **LimitaÃ§Ãµes:** fonte fixa; sem suporte avanÃ§ado.
- **NÃ£o alterar sem reavaliaÃ§Ã£o:** a decisÃ£o de nÃ£o usar TFT_eSPI, a menos que a causa do travamento seja identificada e testada.

### D2. Ãndice da fonte 5Ã—7 = `c*5`, nÃ£o `(c-32)*5`
- **Problema:** letras apareciam trocadas por nÃºmeros/sÃ­mbolos.
- **Causa confirmada:** a fonte Adafruit clÃ¡ssica (256 chars) Ã© indexada por `c*5` (1280 bytes), nÃ£o `(c-32)*5`.
- **SoluÃ§Ã£o:** usar `&font[(uint8_t)c * 5]`.
- **NÃ£o alterar:** o Ã­ndice da fonte.

### D3. ForÃ§ar `ts.isrWake = true` no touch
- **Problema:** o touch nÃ£o lia nada; `touched()` sempre retornava falso.
- **Causa confirmada:** a IRQ (GPIO6) nÃ£o dispara de forma confiÃ¡vel; a biblioteca sÃ³ lia se `isrWake` estivesse true.
- **SoluÃ§Ã£o:** forÃ§ar `ts.isrWake = true` antes de cada leitura.
- **NÃ£o alterar:** a leitura forÃ§ada via `isrWake`.

### D4. CalibraÃ§Ã£o do touch por 2 pontos (sup-esq + inf-dir)
- **Problema:** as coordenadas cruas (0-4095) nÃ£o correspondiam Ã  tela; botÃµes nÃ£o funcionavam.
- **SoluÃ§Ã£o:** assistente de calibraÃ§Ã£o de 2 pontos (tocar no canto sup-esq e inf-dir), salvo em NVS.
- **NÃ£o alterar:** o fluxo de calibraÃ§Ã£o sem reavaliaÃ§Ã£o.

### D5. Usar o `SPI` global compartilhado entre display e touch
- **Problema:** dois `SPIClass` separados no mesmo host corrompiam os dados.
- **SoluÃ§Ã£o:** `ILI9341Driver` usa `_spi = &SPI`; `TouchManager` usa o mesmo `SPI` global.
- **NÃ£o alterar:** o compartilhamento do `SPI` global.

### D6. Redraw condicional (`_needRedraw`)
- **Problema:** redesenhar o dashboard a cada loop causava flicker (~1fps) e texto corrompido.
- **SoluÃ§Ã£o:** `_needRedraw` flag; redraw apenas na mudanÃ§a de estado.
- **NÃ£o alterar:** o mecanismo de redraw condicional.

### D7. `ARDUINO_USB_CDC_ON_BOOT=1`
- **Problema:** serial nÃ£o aparecia de forma estÃ¡vel sem essa flag.
- **SoluÃ§Ã£o:** definir a flag no `build_flags`.
- **ObservaÃ§Ã£o:** ao abrir a porta com pyserial e resetar, o chip entra em download mode â€” usar reset fÃ­sico.

### D8. Board ID correto `esp32-s3-devkitc-1`
- **Problema:** `esp32s3dev` era invÃ¡lido (UnknownBoard).
- **SoluÃ§Ã£o:** usar `esp32-s3-devkitc-1`.
- **NÃ£o alterar:** o board ID sem reavaliaÃ§Ã£o.

### D9. Caminho completo do `pio.exe`
- **Problema:** `pio` nÃ£o estava no PATH.
- **SoluÃ§Ã£o:** usar `C:\Users\mayac\AppData\Roaming\Python\Python313\Scripts\pio.exe` ou adicionar ao PATH.

### D10. `LOG_LEVEL_DEBUG` nÃ£o existe
- **Problema:** compilaÃ§Ã£o falhava.
- **SoluÃ§Ã£o:** usar `LOG_LEVEL_VERBOSE` (a versÃ£o 1.1.1 do ArduinoLog nÃ£o tem DEBUG).

### D11. `ESP.getMaxFreeBlockSize()` nÃ£o existe
- **Problema:** compilaÃ§Ã£o falhava.
- **SoluÃ§Ã£o:** usar `ESP.getHeapSize()`.

### D12. Backlight no GPIO48 conflita com LED RGB
- **Problema:** GPIO48 Ã© o LED RGB da placa.
- **SoluÃ§Ã£o:** usar backlight em 3V3.
- **NÃ£o alterar:** nÃ£o usar GPIO48 como backlight.

---

## 7. Componentes e configuraÃ§Ãµes crÃ­ticas â€” NÃƒO ALTERAR sem justificativa

| Item | Por que Ã© crÃ­tico |
|------|-------------------|
| **Pinagem (BoardConfig.h)** | Baseline oficial; mudar quebra display/touch. |
| **Driver ILI9341 prÃ³prio (SPI bruto)** | TFT_eSPI travava; este driver funciona. |
| **`_spi = &SPI` (SPI global compartilhado)** | Corrompe dados se houver dois SPIClass. |
| **FrequÃªncia SPI 20 MHz (`SPI_DISPLAY_FREQ`)** | FrequÃªncia segura validada; alterar pode causar falhas. |
| **Ãndice da fonte `c*5`** | Letras viram sÃ­mbolos se mudar. |
| **`ts.isrWake = true` forÃ§ado** | Sem isso, o touch nÃ£o lÃª. |
| **`ARDUINO_USB_CDC_ON_BOOT=1`** | Serial via USB. |
| **`_needRedraw` (redraw condicional)** | Sem isso, flicker e texto corrompido. |
| **CalibraÃ§Ã£o 2 pontos + NVS** | Touch sÃ³ funciona apÃ³s calibraÃ§Ã£o. |
| **SequÃªncia de init do ILI9341** | Ordem dos comandos; alterar pode deixar a tela branca. |
| **VersÃµes das libs** | Fixas por reprodutibilidade (ArduinoLog 1.1.1, XPT2046 alpha). |

---

## 8. Problemas, erros e soluÃ§Ãµes

> **Base de conhecimento para troubleshooting.** Formato: sintoma â†’ causa â†’ diagnÃ³stico â†’ soluÃ§Ã£o â†’ prevenÃ§Ã£o.

### P1. `pio` nÃ£o reconhecido
- **Sintoma:** `pio: O termo 'pio' nÃ£o Ã© reconhecido`.
- **Causa:** pio nÃ£o estÃ¡ no PATH.
- **DiagnÃ³stico:** tentar `Get-Command pio` retorna nada.
- **SoluÃ§Ã£o:** usar caminho completo `C:\Users\mayac\AppData\Roaming\Python\Python313\Scripts\pio.exe`.
- **PrevenÃ§Ã£o:** adicionar o diretÃ³rio ao PATH do Windows.

### P2. Board ID invÃ¡lido
- **Sintoma:** `UnknownBoard: Unknown board ID 'esp32s3dev'`.
- **Causa:** board ID errado.
- **SoluÃ§Ã£o:** usar `esp32-s3-devkitc-1`.
- **PrevenÃ§Ã£o:** verificar com `pio boards espressif32`.

### P3. XPT2046_Touchscreen nÃ£o instalÃ¡vel
- **Sintoma:** `UnknownPackageError` para versÃµes como `^1.5.0` / `^1.8.1`.
- **Causa:** versÃ£o nÃ£o existe no registro.
- **SoluÃ§Ã£o:** fixar `0.0.0-alpha+sha.26b691b2c8`.
- **PrevenÃ§Ã£o:** `pio pkg search XPT2046` para achar versÃ£o real.

### P4. ArduinoLog ambÃ­guo
- **Sintoma:** mais de um pacote `ArduinoLog` encontrado.
- **SoluÃ§Ã£o:** usar `thijse/ArduinoLog@1.1.1`.

### P5. `ESP.getMaxFreeBlockSize()` nÃ£o existe
- **Sintoma:** erro de compilaÃ§Ã£o.
- **SoluÃ§Ã£o:** usar `ESP.getHeapSize()`.

### P6. `LOG_LEVEL_DEBUG` nÃ£o definido
- **Sintoma:** erro de compilaÃ§Ã£o.
- **SoluÃ§Ã£o:** usar `LOG_LEVEL_VERBOSE`.

### P7. TFT_eSPI trava em `tft.begin()`
- **Sintoma:** LED RGB parado em magenta (reset loop); display nÃ£o mostra nada.
- **Causa:** travamento na init do TFT_eSPI neste hardware.
- **DiagnÃ³stico:** teste com driver SPI bruto funcionou; TFT_eSPI nÃ£o.
- **SoluÃ§Ã£o:** substituir por `ILI9341_Driver` prÃ³prio (SPI bruto).
- **PrevenÃ§Ã£o:** nÃ£o reintroduzir TFT_eSPI sem investigar a causa.

### P8. Letras trocadas por nÃºmeros/sÃ­mbolos
- **Sintoma:** texto ilegÃ­vel no display.
- **Causa confirmada:** Ã­ndice da fonte `(c-32)*5` em vez de `c*5`.
- **SoluÃ§Ã£o:** corrigir para `c*5`.
- **PrevenÃ§Ã£o:** manter `c*5`.

### P9. Touch nÃ£o detecta nada
- **Sintoma:** `(sem toque detectado)` no serial; touch nunca dispara.
- **Causa confirmada:** a IRQ (GPIO6) nÃ£o dispara; a biblioteca sÃ³ lia se `isrWake=true`.
- **DiagnÃ³stico:** probe SPI manual mostrou o chip respondendo (Z1/Z2 nÃ£o zero) sÃ³ com `isrWake=true`.
- **SoluÃ§Ã£o:** forÃ§ar `ts.isrWake = true` antes da leitura.
- **PrevenÃ§Ã£o:** manter `isrWake=true` na leitura.

### P10. Flicker / 1fps no dashboard
- **Sintoma:** texto piscando, ~1 quadro por segundo.
- **Causa:** redraw completo a cada loop.
- **SoluÃ§Ã£o:** `_needRedraw` condicional.
- **PrevenÃ§Ã£o:** redraw apenas na mudanÃ§a de estado.

### P11. Chip entra em modo download ao abrir serial
- **Sintoma:** captura serial mostra `ESP-ROM... boot:0x0 (DOWNLOAD)` e `waiting for download`.
- **Causa:** abrir a porta USB-Serial/JTAG com pyserial + reset coloca o chip em download mode.
- **SoluÃ§Ã£o:** fechar a porta antes de resetar; usar reset fÃ­sico (RST); nÃ£o tocar DTR/RTS.
- **PrevenÃ§Ã£o:** ao testar via pyserial, usar `s.setDTR(False); s.setRTS(False)` e reset fÃ­sico.

### P12. Tela branca (apenas backlight)
- **Sintoma:** backlight aceso, display sem imagem.
- **Causa:** controlador nÃ£o inicializado (sem init) ou driver errado.
- **SoluÃ§Ã£o:** garantir `ILI9341_Driver::begin()`; usar driver SPI bruto. Tela branca sem init Ã© normal.
- **PrevenÃ§Ã£o:** sempre chamar `begin()` antes de desenhar.

### P13. Backlight em GPIO48 conflita com LED RGB
- **Sintoma:** LED RGB piscando junto com o backlight.
- **Causa:** GPIO48 Ã© o LED RGB da placa.
- **SoluÃ§Ã£o:** backlight em 3V3.
- **PrevenÃ§Ã£o:** nÃ£o usar GPIO48 como backlight.

---

## 9. ReproduÃ§Ã£o do projeto do zero

### Passo 1 â€” Preparar o ambiente
- Windows com PowerShell.
- Python 3.x.

### Passo 2 â€” Instalar as ferramentas
- Instalar VS Code + extensÃ£o PlatformIO (ou usar CLI).
- Instalar PlatformIO Core:
  ```powershell
  python -m pip install --user platformio
  ```
- Localizar o `pio.exe`: `C:\Users\mayac\AppData\Roaming\Python\Python313\Scripts\pio.exe`

### Passo 3 â€” Criar a pasta do projeto
```powershell
New-Item -ItemType Directory -Path C:\Users\mayac\Desktop\esp32_lcd_test
```

### Passo 4 â€” Configurar o `platformio.ini`
Copiar o conteÃºdo da seÃ§Ã£o [4.3](#43-arquivo-platformioini-atual).

### Passo 5 â€” Conectar o hardware
- Conectar o ESP32-S3-DevKitC-1 ao PC via USB (cabo de dados).
- Verificar a porta COM: `powershell -File scripts\detect_esp32_ports.ps1` (ou `pio device list`).

### Passo 6 â€” Reproduzir a pinagem
Seguir exatamente o [Mapa oficial de pinagem](#2-mapa-oficial-de-pinagem-do-projeto):
- GPIO11=MOSI, GPIO12=SCK, GPIO13=MISO, GPIO10=CS display, GPIO9=DC, GPIO8=RST, GPIO7=CS touch, GPIO6=IRQ touch (opcional).
- Backlight em 3V3. **NÃ£o** usar GPIO48 como backlight.

### Passo 7 â€” Configurar os drivers
- Os drivers estÃ£o no projeto (ILI9341_Driver, TouchManager). DependÃªncias sÃ£o baixadas automaticamente pelo `lib_deps`.

### Passo 8 â€” Compilar
```powershell
C:\Users\mayac\AppData\Roaming\Python\Python313\Scripts\pio.exe run -d C:\Users\mayac\Desktop\esp32_lcd_test
```

### Passo 9 â€” Gravar o firmware
```powershell
C:\Users\mayac\AppData\Roaming\Python\Python313\Scripts\pio.exe run -t upload -e esp32s3 -d C:\Users\mayac\Desktop\esp32_lcd_test --upload-port COM3
```
(Substitua COM3 pela porta real.)

### Passo 10 â€” Abrir o monitor
```powershell
C:\Users\mayac\AppData\Roaming\Python\Python313\Scripts\pio.exe device monitor -p COM3 -b 115200
```
> **AtenÃ§Ã£o:** se a porta abrir e o chip entrar em modo download, pressione **RST** fÃ­sico na placa.

### Passo 11 â€” Validar o LCD
- O display deve mostrar o dashboard (ou a tela de calibraÃ§Ã£o se o touch nÃ£o estiver calibrado).
- Se a tela ficar branca, verificar `begin()` e a pinagem.

### Passo 12 â€” Executar os testes
- Calibrar o touch (assistente de 2 pontos) se necessÃ¡rio.
- Usar comandos serial: `touch`, `diag`, `display`, `calibrate`, `home`.

### Passo 13 â€” Confirmar o resultado
- Dashboard legÃ­vel, sem flicker.
- Touch responde (cursor segue o dedo apÃ³s calibraÃ§Ã£o).

---

## 10. Checklist de validaÃ§Ã£o

| # | Teste | CritÃ©rio de aprovaÃ§Ã£o |
|---|-------|----------------------|
| 1 | **InicializaÃ§Ã£o** | Boot sem reset loop; LED RGB pisca (indicador) |
| 2 | **Serial** | `PING`/`PONG` ou comandos respondem (115200) |
| 3 | **LCD cores** | Tela vermelha/verde/azul visÃ­vel (teste `FILL`) |
| 4 | **LCD texto** | Dashboard legÃ­vel, sem sÃ­mbolos trocados |
| 5 | **LCD rotaÃ§Ã£o** | RotaÃ§Ã£o 0 (240Ã—320) correta |
| 6 | **GPIOs** | Pinos CS/DC/RST operam (display funciona) |
| 7 | **Touch init** | `probeRaw` retorna CHIP RESPONDE (Z1/Z2 != 0) |
| 8 | **Touch calibraÃ§Ã£o** | Assistente 2 pontos completa; cursor segue dedo |
| 9 | **NavegaÃ§Ã£o** | Comandos serial `touch`/`diag`/`home` mudam a tela |
| 10 | **Estabilidade** | 30s+ sem crash/flicker |
| 11 | **ReinicializaÃ§Ã£o** | RST fÃ­sico â†’ app roda (sem modo download) |
| 12 | **PersistÃªncia** | CalibraÃ§Ã£o sobrevive a reset (NVS) |
| 13 | **AlimentaÃ§Ã£o** | Sem brownout; display estÃ¡vel |

---

## 11. PadrÃ£o base para projetos ESP32 + LCD

> **Gatilho de uso:** *"Crie um novo projeto ESP32 + LCD seguindo o padrÃ£o deste projeto."*

### 11.1 Arquitetura recomendada
- **Camadas:** Config â†’ Driver de hardware â†’ Manager (alto nÃ­vel) â†’ UI/Estados â†’ main.
- **SeparaÃ§Ã£o clara:** configuraÃ§Ã£o (AppConfig/BoardConfig), hardware (driver), manager (DisplayManager/TouchManager), testes (Diagnostics/TestRunner), UI (UiManager).
- **SPI compartilhado:** display + perifÃ©ricos no mesmo barramento usam o `SPI` global + transaÃ§Ãµes.

### 11.2 OrganizaÃ§Ã£o dos arquivos
```
include/  (headers de todos os mÃ³dulos)
src/      (implementaÃ§Ãµes)
scripts/  (automaÃ§Ã£o PowerShell/Python)
.vscode/  (tasks/settings)
platformio.ini
TECHNICAL_REFERENCE.md
```

### 11.3 ConvenÃ§Ãµes
- `BoardConfig.h` para pinos; `AppConfig.h` para constantes.
- Nomes descritivos; comentÃ¡rios curtos; sem pseudocÃ³digo.
- PortuguÃªs nos comentÃ¡rios do projeto.

### 11.4 EstratÃ©gia de pinagem
- Usar pinos padrÃ£o da variante sempre que possÃ­vel (SPI: MOSI/SCK/MISO padrÃ£o).
- Documentar pinos no BoardConfig.h e no mapa oficial.
- Evitar GPIO48 (LED RGB) para outros usos sem justificativa.

### 11.4 EstratÃ©gia de drivers
- Preferir driver de baixo nÃ­vel prÃ³prio quando a biblioteca padrÃ£o falhar.
- Fixar versÃµes de libs no `lib_deps`.
- Documentar drivers testados/descartados.

### 11.5 Processo de testes
- Firmware de sonda (probe) para isolar hardware.
- Testes visuais (cores, texto) + serial.
- Pipeline de diagnÃ³stico (`Diagnostics::runFull`).

### 11.7 Processo de documentaÃ§Ã£o
- Manter `TECHNICAL_REFERENCE.md` atualizado com decisÃµes, pinagem, problemas.
- Atualizar quando alterar pinos, drivers ou configuraÃ§Ãµes.

### 11.8 Checklists

**Hardware:**
- [ ] Placa ESP32-S3 conectada via cabo de dados
- [ ] Backlight em 3V3 (nÃ£o GPIO48)
- [ ] Pinagem conforme mapa oficial
- [ ] Porta COM detectada

**Software:**
- [ ] `platformio.ini` correto
- [ ] `lib_deps` com versÃµes fixas
- [ ] Compila sem erros
- [ ] Upload OK

**IntegraÃ§Ã£o:**
- [ ] Dashboard legÃ­vel
- [ ] Touch calibrado e respondendo
- [ ] Comandos serial funcionando
- [ ] Estabilidade

---

## 12. Compatibilidade e reutilizaÃ§Ã£o

| Componente | ClassificaÃ§Ã£o |
|------------|---------------|
| **ILI9341_Driver** (driver SPI bruto) | **ReutilizÃ¡vel diretamente** (com pinos ajustados) |
| **DisplayManager** | **ReutilizÃ¡vel com adaptaÃ§Ã£o** (acopla ao driver) |
| **TouchManager + calibraÃ§Ã£o 2 pontos** | **ReutilizÃ¡vel com adaptaÃ§Ã£o** |
| **UiManager (mÃ¡quina de estados)** | **ReutilizÃ¡vel com adaptaÃ§Ã£o** |
| **Diagnostics / TestRunner** | **ReutilizÃ¡vel com adaptaÃ§Ã£o** |
| **Font5x7.h** | **ReutilizÃ¡vel diretamente** |
| **BoardConfig.h (pinagem especÃ­fica)** | **EspecÃ­fico deste hardware** |
| **AppConfig.h** | **EspecÃ­fico deste projeto** (ajustar valores) |
| **SequÃªncia de init do ILI9341** | **EspecÃ­fico deste driver/display** |
| **XPT2046_Touchscreen (lib)** | **ReutilizÃ¡vel diretamente** (touch XPT2046) |
| **ArduinoLog** | **ReutilizÃ¡vel diretamente** |
| **TFT_eSPI** | **NÃ£o recomendado para reutilizaÃ§Ã£o** neste hardware (travava) |
| **Scripts PowerShell** | **ReutilizÃ¡veis com adaptaÃ§Ã£o** (nomes de arquivo/pasta) |
| **probe_display.py** | **ReutilizÃ¡vel com adaptaÃ§Ã£o** |

---

## 13. Estado atual do projeto

### Funcionando / validado
- [x] CompilaÃ§Ã£o e upload OK (PlatformIO).
- [x] Display ILI9341 funcionando via driver SPI bruto (cores + texto).
- [x] Texto 5Ã—7 legÃ­vel (fonte corrigida).
- [x] Touch XPT2046 detectado (CHIP RESPONDE via probe).
- [x] CalibraÃ§Ã£o do touch por 2 pontos (funcionando â€” "ainda nÃ£o perfeitamente", segundo o usuÃ¡rio).
- [x] Dashboard e navegaÃ§Ã£o por estados.
- [x] Comandos serial de navegaÃ§Ã£o.
- [x] Interface sem flicker (redraw condicional).

### Pendente / em validaÃ§Ã£o
- [ ] **CalibraÃ§Ã£o fina do touch** (o usuÃ¡rio indicou que "funciona, ainda nÃ£o perfeitamente" â€” **EM VALIDAÃ‡ÃƒO**).
- [ ] **BotÃµes funcionando via toque** (depende da calibraÃ§Ã£o fina).
- [ ] **DiagnÃ³stico completo via menu** (pipeline parcialmente implementada).
- [ ] **TestRunner** (registro/execuÃ§Ã£o parcial).

### NÃ£o testado / nÃ£o confirmado
- [ ] **PSRAM real** (esptool reportou 8MB; board define sem PSRAM) â€” **NECESSITA VALIDAÃ‡ÃƒO**.
- [ ] **Flash real** (esptool reportou 16MB; board define 8MB) â€” **NECESSITA VALIDAÃ‡ÃƒO**.
- [ ] **Wi-Fi / Bluetooth** â€” nÃ£o usado.
- [ ] **LittleFS/SPIFFS** â€” nÃ£o usado.
- [ ] **Leitura de ID do controlador** via registro (nÃ£o usada; driver usa init fixo).
- [ ] **Consumo de energia** â€” nÃ£o medido.

### LimitaÃ§Ãµes conhecidas
- Driver ILI9341 sem fontes vetoriais/DMA.
- Touch precisa de calibraÃ§Ã£o (nÃ£o Ã© plug-and-play).
- IRQ do touch nÃ£o confiÃ¡vel (forÃ§a `isrWake`).
- GPIO48 Ã© LED RGB (nÃ£o usar como backlight).

### PrÃ³ximos passos
1. Refinar a calibraÃ§Ã£o do touch para os botÃµes funcionarem de forma confiÃ¡vel.
2. Validar PSRAM/Flash real (confirmar mÃ³dulo).
3. Implementar pipeline de diagnÃ³stico acessÃ­vel pelo menu.
4. Implementar TestRunner completo.
5. PossÃ­vel extensÃ£o: suporte a rotaÃ§Ã£o paisagem, fontes maiores, gestos.

---

## 14. Formato final

Este documento Ã© a **referÃªncia tÃ©cnica oficial** do projeto. Foi organizado em formato profissional com:
- Ãndice navegÃ¡vel.
- SeÃ§Ãµes de visÃ£o geral, arquitetura, hardware, pinagem, drivers, software, configuraÃ§Ã£o, instalaÃ§Ã£o, execuÃ§Ã£o, testes, troubleshooting, decisÃµes, padrÃ£o reutilizÃ¡vel, checklist, estado atual e prÃ³ximos passos.

**PrincÃ­pios seguidos:**
- Dados **concretos e verificÃ¡veis** (versÃµes, pinos, comandos reais).
- InformaÃ§Ãµes nÃ£o confirmadas marcadas como **NÃƒO CONFIRMADO** ou **NECESSITA VALIDAÃ‡ÃƒO**.
- Nada inventado: tudo descrito aqui foi observado/executado no desenvolvimento.

---

*Fim da referÃªncia tÃ©cnica. Documento gerado para preservar o conhecimento e servir de base para futuros projetos ESP32 + LCD.*
