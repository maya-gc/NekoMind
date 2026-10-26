# Validação de áudio e presença de fala

Depois da finalização manual, antes de transcrever/avaliar, o modo real exige WAV
PCM16 mono a 16 kHz, íntegro e não vazio. O detector é **WebRTC VAD**, via
`webrtcvad-wheels==2.0.14`, modo de agressividade **2**, frames de **30 ms** e
mínimo acumulado de **10 frames positivos (300 ms)**. Não usa volume ou tamanho de
arquivo isoladamente como prova de fala. Implementação: `audio_processing.validate_speech`.

São inspecionados metadados, número de amostras, conteúdo integral do WAV e qualidade
compacta. `audio_quality.assess_audio_quality` classifica pico/nível, clipping, baixo
nível e ruído excessivo antes da análise pedagógica. Clipping persistente e ruído
excessivo bloqueiam avaliação real; nível baixo gera orientação operacional e pode
exigir calibração conforme o estado do detector. Os chunks PCM precisam ser consecutivos,
sem duplicação, no formato informado. O limite é 30 minutos de áudio. A cauda inferior
a um frame não entra na contagem de VAD. Dependência ausente ou erro do detector é
falha explícita, sem aprovação automática.

Não se exige proporção mínima de fala na sessão: pausas de raciocínio são permitidas.
O detector só roda após finalizar; não encerra por silêncio nem mantém escuta contínua.
Ausência de fala/voz insuficiente produz erro recuperável de captura, sem nota de
conhecimento, tópicos ou conclusão. O modo demo aceita silêncio e mantém sua etiqueta.

## Evidência e calibração pendente

`test_speech_validation.py` usa o **WebRTC instalado** para silêncio e ruído branco
sintético determinístico. Para testar fronteiras de duração, clipping, nível baixo e
pausas, injeta um **substituto do detector**. Esses últimos testes verificam a política,
não a capacidade acústica do WebRTC. O teste integrado real usa ASR e detector
substitutos e extrator local executado.

Ainda é necessário calibrar com fala real, sussurro, distância, ventilador, música e
pausas no Mac escolhido. WebRTC pode produzir falsos positivos e negativos; não prova
qualidade de captação, correção factual ou domínio. Registrar hardware, microfone,
distância, ambiente, parâmetros e falhas no [roteiro de mesa](manual-validation.md).

Fonte do detector e licença: [webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels)
(MIT no wrapper; avisos de terceiros para código WebRTC). Nenhum áudio é enviado à nuvem.
