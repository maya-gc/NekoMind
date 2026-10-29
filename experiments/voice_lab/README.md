# Voz local em português brasileiro: prova no Mac

Teste de bancada em 2026-10-08, no Mac Apple Silicon do projeto, usando MPS.
O áudio é gerado localmente após baixar os pesos uma vez. As duas amostras de
comparação usam a mesma frase e têm volume normalizado. A naturalidade do timbre
é uma avaliação auditiva e continua pendente de escolha pelo usuário.

| Modelo | Pesos em cache | Preparação com pesos em cache | Frase aquecida | Áudio gerado |
| --- | ---: | ---: | ---: | ---: |
| Kokoro 82M (`pf_dora`, pt-BR) | 327 MB | 2,4 s | 0,7 s | 3,33 s |
| Chatterbox V3 específico pt-BR | 3,0 GB | 8,9 s | 5,6 s | 3,40 s |

Esses tempos são amostras desta máquina, não garantias de produção. A primeira
geração também aquece bibliotecas e GPU: 3,4 s no Kokoro e 8,8 s no Chatterbox
na segunda rodada. O Chatterbox havia levado 27,8 s no primeiro teste frio.

A frase de comparação, “Que legal! E o que acontece com o vapor quando ele
esfria?”, foi recuperada integralmente pela transcrição local Whisper `base`
em ambos. O nome “NekoMind” não foi recuperado com clareza em nenhuma das duas
vozes; é necessário testar uma escrita de pronúncia ou outra referência de voz.
Com os pesos já em cache, os dois modelos também geraram “Olá!” com
`HF_HUB_OFFLINE=1`, confirmando que a síntese não depende de uma API remota.

## Arquivos para ouvir

- `output/audio/nekomind-kokoro-ptbr-followup-preview.wav`
- `output/audio/nekomind-chatterbox-ptbr-followup-preview.wav`

Os arquivos `*-preview.wav` têm volume normalizado. Os WAVs sem `preview`
preservam o sinal original do sintetizador.

## Reproduzir

1. Instalar `espeak-ng` no Mac (`brew install espeak-ng`).
2. Criar ambientes Python 3.11 separados para Kokoro e Chatterbox.
3. Instalar `kokoro==0.9.4`, `soundfile` e `transformers>=4.45,<5` no ambiente
   Kokoro. O limite explícito de Transformers evita uma versão antiga que tenta
   compilar `tokenizers` sem Rust.
4. Instalar `chatterbox-tts==0.1.7` e `setuptools==80.9.0` no ambiente
   Chatterbox. A dependência `resemble-perth` ainda importa `pkg_resources`.
5. Clonar o Space oficial pt-BR em `chatterbox-ptbr-space`:
   `git clone --depth 1 https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br`.
6. Executar `generate_kokoro_ptbr.py` ou `generate_ptbr.py` com
   `PYTORCH_ENABLE_MPS_FALLBACK=1` e `HF_HUB_DISABLE_XET=1`.

O código do Chatterbox pt-BR vem do Space oficial; o pacote `chatterbox-tts`
sozinho carrega o modelo multilíngue geral. O `PYTHONPATH` deve apontar para
`chatterbox-ptbr-space/chatterbox/src` ao usar `generate_ptbr.py`.

Fontes: [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M),
[Chatterbox pt-BR](https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br),
[Space pt-BR](https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br).
