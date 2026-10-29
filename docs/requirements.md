# Requisitos do NekoMind — MVP touch + Mac

## Fluxo aprovado

1. A pessoa toca em comecar no ESP32 com display touch.
2. O Mac inicia de fato a captura pelo microfone local e confirma.
3. O gatinho mostra gravando somente apos confirmacao do Mac.
4. Pausar/retomar/finalizar pelo touch altera a captura real no Mac.
5. O Mac encerra a captura, valida audio/fala, transcreve, extrai assuntos, calcula metricas heuristicas e persiste.
6. O gatinho recebe apenas resultado validado da sessao atual. Erro, timeout, resposta antiga ou resposta de outra sessao nao sao sucesso.

## Requisitos funcionais

- Touch obrigatorio como interface operacional da sessao.
- Mac como fonte de audio no caminho principal.
- USB/serial JSON Lines para comandos, estados, erros e resultados.
- Demo util e identificado; modo real falha fechado, sem fallback silencioso para mock.
- ASR lazy/cache por processo e configuracao.
- Validacao de audio/fala antes de avaliar no modo real.
- Idempotencia para inicio, upload de chunks e finalizacao.
- Extracao local de topicos fundamentada na transcricao, sem quantidade fixa inventada.
- SQLite local com migracao aditiva para bancos MVP existentes.

## Fora de escopo

- Gravador pelo navegador.
- Audio vindo do ESP no caminho principal.
- Escolha de placa, display, touch controller, pinos e tamanho.
- Microfone embarcado, Wi-Fi e dispositivo independente do Mac.
- Envio de audio/transcricao real para nuvem ou contratacao de servicos.
- Avaliacao pedagogica definitiva.

## Evidencia esperada

Testes automatizados cobrem contratos de backend, bridge, VAD sintetico, idempotencia e falhas. Validacao fisica exige roteiro manual com hardware escolhido, microfone real, permissao macOS e modelo ASR real/local.
