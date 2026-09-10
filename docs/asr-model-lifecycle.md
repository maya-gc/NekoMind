# Ciclo de vida do ASR (NM-002)

O modo demo usa MockASRAdapter, sem importar faster-whisper. O modo real usa
FasterWhisperAdapter, com modelo previamente disponível em disco/cache. A primeira
transcrição carrega o modelo lazy. O cache é por processo e pela tripla
(modelo/caminho, dispositivo, compute_type). Um RLock protege inicialização, uso,
consumo completo do gerador de segmentos e cleanup. Inicialização que falha não
publica entrada no cache. O idioma permanece português (`language="pt"`).

O lifespan FastAPI chama clear_asr_cache no encerramento, com atexit como proteção
adicional. O cleanup aguarda o uso ativo, descarrega o modelo nativo CTranslate2 e
remove referências. Não há promessa de redução imediata de RSS pelo alocador do SO.
No MVP, executar um worker e sem reload durante sessões: cada processo tem seu cache.

## Medir sem inventar benchmark

Registrar macOS, arquitetura/chip, RAM, Python, faster-whisper/CTranslate2, modelo e
revisão/caminho, device e compute_type. Usar o mesmo WAV sintético ou autorizado
localmente; não versionar gravações. Com processo novo, medir com perf_counter o
intervalo que inclui consumo de todos os segmentos na primeira transcrição; repetir
no mesmo processo e registrar tempos individuais das seguintes. Medir também RSS
antes/depois e pico com Activity Monitor ou `/usr/bin/time -l`; não confundir pico
de processo com memória exclusiva do modelo. Repetir em processos novos e reportar
amostra, dispersão e condições. Separar VAD, ASR e pipeline completo.

Testes automatizados: `cd backend && .venv/bin/python -m unittest discover -s tests
-p test_asr_lifecycle.py -v` e `pytest`. Eles usam modelo substituto e não comprovam
desempenho, precisão ou compatibilidade de um modelo real neste Mac.

Fonte: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), consultada em
2026-09-10; segmentos são um gerador, portanto o lock cobre também a iteração.
