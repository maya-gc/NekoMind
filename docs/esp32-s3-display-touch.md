# Protótipo físico ESP32-S3 + ILI9341/XPT2046

A branch remota `pipeline` (commit `0f263b3`) contém documentação e uma referência
de pinagem para a unidade de MAC `d8:3b:da:43:19:90`. Ela **não contém** os arquivos
`src/`, `lib/` ou `include/` citados no README dessa branch. Por isso não foi feito
merge de um firmware inexistente: a pinagem e as observações úteis foram aplicadas
ao alvo ESP-IDF já existente nesta branch. O protótipo conectado foi identificado
como ESP32-S3 rev. 0.2, USB Serial/JTAG, com 8 MB de PSRAM reportados pelo esptool.
A revisão exata do módulo, o tamanho útil da flash e a qualidade do touch ainda
precisam de confirmação física.

## Ligações usadas pelo protótipo

| Sinal | GPIO |
|---|---:|
| SPI MOSI / SCK / MISO compartilhados | 11 / 12 / 13 |
| ILI9341 CS / DC / RST | 10 / 9 / 8 |
| XPT2046 CS | 7 |
| XPT2046 IRQ | 6 (não usado; leitura por polling) |
| Backlight | 3V3 no protótipo documentado |

Não usar GPIO48 como backlight: no DevKitC-1 da referência ele é o LED RGB.
LCD e touch usam o mesmo barramento SPI2, com dispositivos/CS separados (20 MHz
para LCD, 2 MHz para touch). O firmware desenha diretamente em RGB565 com fonte
5×7, em 240×320 na orientação retrato. Os estados e eventos continuam na lógica
portátil; `board_spi.c`, `display_ui.c` e `board_touch.c` são específicos desta
unidade e da pinagem acima.

## Compilar, gravar e observar

Instale ESP-IDF v5.3.1 e seus submódulos no `esp-idf/` local, a toolchain com
`bash esp-idf/install.sh esp32s3`, além de CMake e Ninja. Na raiz do repositório:

```bash
source scripts/source_idf.sh
cd iot/nekomind_firmware
idf.py set-target esp32s3    # somente na primeira configuração local
idf.py build
idf.py -p /dev/cu.usbmodem101 flash
idf.py -p /dev/cu.usbmodem101 monitor
```

Confirme a porta com `python -m serial.tools.list_ports`. Somente um processo pode
usar a porta; feche o monitor antes de iniciar o bridge. Se o app anterior estiver
reiniciando sem parar e o reset automático não conseguir entrar no bootloader,
segure **BOOT**, aperte e solte **RST/EN** e solte **BOOT**; então repita o flash.
Não apague NVS para resolver isso: ela guarda a calibração.

O LCD deve mostrar o rosto e os botões do estado atual. Antes do Mac confirmar
`ready`, o início fica bloqueado e o dispositivo oferece diagnóstico. Para o fluxo
completo, configure backend local e bridge conforme o README. O Mac captura áudio;
o ESP troca somente JSON Lines. O botão **Calibrar** da sessão é a calibração do
microfone do Mac, diferente da calibração física do touch descrita abaixo.

## Calibrar touch físico

O mapeamento inicial é aproximado. Com backend/bridge/monitor **fechados**, envie
uma vez `!touch-calibrate\n` a 115200 baud pela porta USB. O LCD mostra três alvos:
superior esquerdo, superior direito, inferior esquerdo. Toque e solte cada um;
há 30 segundos por alvo. O firmware mede direção e escala, grava os limites no NVS
e restaura a tela anterior. Se expirar ou a leitura falhar, preserva a calibração
anterior. Depois feche o terminal serial e inicie o bridge.

Exemplo de envio, executado na raiz do repositório:

```bash
backend/.venv/bin/python - <<'PY'
import serial
import time
port = serial.Serial(port=None, baudrate=115200, timeout=1)
port.dtr = False
port.rts = False
port.port = '/dev/cu.usbmodem101'
with port:
    time.sleep(1)  # aguardar eventual reinicio ao abrir USB Serial/JTAG
    port.write(b'!touch-calibrate\n')
    port.flush()
    for _ in range(100):
        line = port.readline()
        if line:
            print(line.decode('utf-8', 'replace').rstrip())
PY
```

Esse comando é manutenção local, separado do protocolo JSON v1 do Mac. O teste
automatizado valida controlador e layout; não substitui observar pixels, toque,
orientação e contraste na unidade real. Use o [roteiro de mesa](manual-validation.md)
e registre o que foi visto antes de considerar a apresentação física validada.

## Evidência desta integração (21/09/2026)

`esptool chip_id` confirmou ESP32-S3 rev. 0.2 e o MAC acima; `idf.py build` passou.
O flash da imagem corrigida verificou o hash de bootloader, app e partição. A
primeira gravação revelou falha de `fcntl` no console USB; a segunda revelou
stack overflow na main ao montar a cena. Ambas foram corrigidas. Foi necessário
vincular o VFS USB Serial/JTAG para receber respostas do Mac. O touch XPT2046 foi
calibrado em três pontos e a calibração ficou no NVS.

Na gravação de 21/09, a pessoa na bancada confirmou o gatinho estável, os botões
Diagnóstico, Começar, Pausar, Retomar e Finalizar, o resultado demo e Nova tentativa.
O Mac confirmou as transições e persistiu a sessão com chunks de microfone. Um
primeiro ensaio interrompia a captura após ~8 s: eventos de voz adiavam o
heartbeat indefinidamente. O firmware corrigido manteve comandos `status` a cada
~2 s durante a gravação, e a sequência completa passou. O bridge também passou
a reconciliar a sessão anterior após desconexão; estado `recovery` agora usa um
quadro `state` aceito pelo parser do firmware. Esse primeiro resultado da bancada
foi demo, com ASR e extração mock. Em um ensaio posterior no mesmo dia, uma sessão
real com fala humana terminou no LCD como captura e processamento concluídos; o Mac
confirmou ASR local, extração local e persistência com `is_demo=false`. A qualidade
da transcrição e dos termos ainda exige avaliação com mais vozes e ambientes.

Quando o reset automático falhar, entre no bootloader com BOOT+RST e grave com
`esptool --before no_reset --after no_reset write_flash @flash_args` dentro de
`iot/nekomind_firmware/build`; depois aperte RST/EN sem BOOT. Não apague NVS.
