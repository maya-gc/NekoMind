# Laboratório de viabilidade embarcada do NekoMind

Este firmware isolado roda no QEMU para ESP32-S3 e mede alocações de memória por etapa.
Ele **não** contém modelos de ASR, LLM ou TTS; injeta uma frase de teste e faz uma busca
lexical mínima. Não mede velocidade real, microfone, alto-falante, touch, LCD ou SD.

O perfil de flash de 2 MB reflete a configuração de build atual do NekoMind, não a
capacidade física comprovada do módulo. O QEMU recebe 8 MB de PSRAM octal hipotéticos.

## Reproduzir no ambiente local

1. Usar ESP-IDF v5.3.1 e instalar QEMU Xtensa da Espressif.
2. Exportar `IDF_PATH`, `IDF_TOOLS_PATH` e o ambiente Python do ESP-IDF.
3. Dentro desta pasta: `idf.py set-target esp32s3 && idf.py build`.
4. Criar imagem completa com `python -m esptool --chip esp32s3 merge_bin
   --fill-flash-size 2MB -o build/lab_flash.bin @build/flash_args`.
5. Rodar QEMU recente: `qemu-system-xtensa -nographic -machine esp32s3 -m 8M
   -global driver=ssi_psram,property=is_octal,value=true
   -drive file=build/lab_flash.bin,if=mtd,format=raw`.

Os registros `ARENA` indicam apenas se um bloco contínuo de PSRAM pôde ser alocado.
Modelos reais têm pesos, buffers, DMA, tarefas, caches e padrões de acesso próprios.
O experimento precisa ser refeito em placa com áudio, LCD e SD funcionando juntos.

## Resultado desta rodada

O registro estruturado está em [`results/2026-10-06.json`](results/2026-10-06.json).
No QEMU 9.2.2, o firmware inicializou com 8 MB de PSRAM simulados. Após alocar
um anel PCM de 128 kB, um índice de texto de 256 KiB e uma faixa RGB565 de
9,6 kB, restaram 7.995.568 bytes de PSRAM livres. Blocos de 2,4, 5,4 e
6,5 MiB foram alocados separadamente; 5,4 + 6,5 MiB simultâneos não couberam.
Esses blocos **não são os modelos**: servem para testar a política de memória.

Uma voz portuguesa `sanoTTS pt-cadu-0p51m` gerou três arquivos WAV no Mac.
Essa prova é apenas de síntese no host. O peso local de `faster-whisper` estava
incompleto, então a inteligibilidade não foi verificada. Não foi executado
TTS português no QEMU nem no ESP32-S3 físico.
