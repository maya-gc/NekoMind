# NekoMind Firmware

Firmware do dispositivo NekoMind para o MVP touch + Mac.

O caminho principal aprovado e:

- ESP32 com display touch: avatar, comandos de sessao e resultado curto.
- Mac: captura do microfone, transcricao, validacao, analise e persistencia.
- USB/serial: JSON Lines v1 para comandos, estados, erros e resultados.
- Sem transporte de audio pelo ESP no fluxo principal do MVP.

O microfone embarcado/I2S permanece no repositorio como possibilidade futura,
mas os arquivos `audio_capture.c` e `i2s_microphone.c` nao entram no alvo
principal do firmware neste MVP.

## Estados

`IDLE -> PENDING -> CHECKING -> READY -> RECORDING -> PAUSED -> PROCESSING -> SUCCESS | ERROR`

`RECOVERY` e um estado explicito quando Mac/backend informam sessao
interrompida. O firmware mostra a bifurcacao de retomada/descarte e nunca
reativa captura sozinho.

O firmware so entra em `RECORDING` depois de receber estado `recording`
correlacionado do Mac. Ele so entra em `SUCCESS` depois de receber um
`type=result`, `state=completed`, com `request_id` e `session_id` da sessao
atual e campos obrigatorios validados. Mensagens antigas, de outra sessao,
malformadas, erros tardios ou simuladas como reais nao produzem sucesso.

## Contrato serial

As mensagens seguem JSON Lines UTF-8, ate 4096 bytes por linha. O dispositivo
envia comandos:

```json
{"v":1,"type":"command","request_id":"req-1","command":"start","session_id":null}
```

Comandos suportados: `start`, `pause`, `resume`, `finish`, `retry`, `status`,
`diagnose`, `calibrate`, `recover`, `discard`, `cancel`, `reset` e reenvio
local da ultima requisicao. O `request_id` inclui nonce de boot de
128 bits injetado pelo ESP (`esp_random` quatro vezes) mais contador monotono,
para evitar colisao com o journal do Mac apos reboot. Reenvio preserva
exatamente o mesmo `request_id` para idempotencia quando a confirmacao se
perde.

Heartbeats `status` sao rastreados separadamente do `finish`: eles atualizam
a conexao, mas nao substituem o `request_id` aguardado para o resultado final
e nao reiniciam indefinidamente o timeout de analise. Se um heartbeat durante
`PROCESSING` receber o resultado ja persistido, o firmware aceita esse resultado
correlacionado dentro do prazo.

`session_id:null` e aceito somente para `state=idle` e para erro correlacionado
ao `start` quando o backend/Mac ainda nao abriu sessao. Resultados continuam
exigindo `session_id` positivo. Estados de confirmacao tambem precisam
corresponder ao comando pendente; por exemplo, `pause` nao aceita `recording`
como confirmacao.

O Mac responde com `type=state`, `type=error` ou `type=result`. Resultado:

```json
{
  "v": 1,
  "type": "result",
  "request_id": "bootNonce-2",
  "session_id": 42,
  "state": "completed",
  "is_demo": false,
  "asr_provider": "faster_whisper",
  "topic_provider": "local_keywords",
  "topics": ["fotossintese"],
  "summary": "Sessao processada."
}
```

Topicos vazios sao validos. O firmware nao mostra nota pedagogica; a cena
ILI9341 recebe estado, resumo curto, topicos e origem demo/real conforme `is_demo`.

Contrato aditivo NM-019: o `result` v1 essencial acima permanece valido. O Mac
pode enviar campos opcionais `duration_seconds`, `subject` e `trend_text`; o
firmware novo usa esses campos para cards touch de duracao/evolucao, e firmwares
antigos podem ignorar a extensao. O Mac tambem pode anexar `voice` em estados
com `{level:0..100, clipping:bool, quality:"ok"|"low"|"clipping"|"unknown"}` e
`journey` com `status:"waiting"|"running"|...`. Essas extensoes nunca produzem
sucesso; `SUCCESS` continua exigindo `type:"result"`, `state:"completed"`,
`request_id` correlacionado, `session_id` atual e provedores validos.

Quando `PROCESSING` recebe `journey.status` `waiting` ou `running`, o timeout
de resultado e renovado de forma limitada ate `NEKO_PROCESSING_MAX_MS`
(10 minutos). Sem progresso real, o timeout antigo de 120s continua gerando
erro recuperavel.

## Layout touch portatil

`neko_layout.c` calcula um modelo independente de driver para 240x320 e
320x240, gera uma display list com primitivas proprias do rosto felino
(`FACE`, elipses, poligonos, linhas, textos e botoes) e expõe `hit_test` para
mapear coordenadas futuras do touch em eventos do controlador. O rosto permanece
presente nos estados centrais, botoes tem alvos de pelo menos 44px e
`prefers-reduced-motion` pode manter o rosto estatico.

Os cards de resultado sao paginados localmente e montados somente quando dados
existem: resumo, termos reconhecidos agrupados, duracao e evolucao. A navegacao
de cards nao envia comando remoto
nem muda a sessao. A tela `IDLE` nao oferece `Comecar`; primeiro passa por
diagnostico e so exibe inicio quando o Mac confirma `READY`. `cancel`,
`discard` e `reset` exigem confirmacao local por segundo toque antes de emitir
comando, e o detector de borda evita que segurar o dedo confirme duas vezes. O
driver fisico atual desenha esse modelo no ILI9341 240x320.

O log serial de diagnostico nao imprime resumo, topicos nem transcricao; ele
registra inicializacao e estados de hardware. O bridge ignora linhas que nao sao
JSON valido.

## Protótipo físico

O alvo atual é o ESP32-S3 de MAC `d8:3b:da:43:19:90` com ILI9341/XPT2046,
conforme [pinagem e instruções](../../docs/esp32-s3-display-touch.md) derivadas
da branch `pipeline`. O touch é lido por polling SPI; GPIO6/IRQ não é necessário.
Os limites iniciais de coordenadas são aproximados. `!touch-calibrate` pelo serial
mede três pontos e salva calibração no NVS. O comando JSON `calibrate` continua
reservado à calibração do microfone do Mac.

A main task e a task de sessão têm stack de 12288 bytes para montar a cena
240x320. O buffer RX de até 4096 bytes é estático. A compilação e a gravação
foram exercitadas na unidade USB, mas isso não substitui inspeção visual, toque
e teste completo com bridge/microfone/modelo real.

## Teste host

O teste automatizado valida a logica independente de hardware:

```bash
iot/nekomind_firmware/scripts/test_firmware.sh
```

Ele cobre conclusao valida, mensagens invalidas/antigas/de outra sessao,
timeouts, erro, pausa/retomada, toque duplo, nova tentativa, nonce por boot,
reenvio da mesma requisicao, `session_id:null` restrito, estado inesperado em
ack de comando, heartbeat durante processamento, wrap de `millis` e resultado
direto sem estado `processing` intermediario.

## Build ESP-IDF

```bash
source scripts/source_idf.sh
cd iot/nekomind_firmware
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/cu.usbmodem101 flash
```

O layout portatil tambem suporta 320x240, mas o driver fisico desta unidade
renderiza 240x320. A validacao visual e do touch ainda e obrigatoria.
