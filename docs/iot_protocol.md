# Contrato USB/serial v1 — touch + Mac

JSON Lines UTF-8, uma mensagem por LF, até4096 bytes incluindo LF, baud115200.
O driver deve reservar terminador NUL no C. Sem áudio do ESP nesse canal. Logs de
hardware devem ficar separados ou claramente descartados; não são respostas válidas.
O transporte RX físico depende da placa; os testes host não comprovam USB físico.

## Comandos

```json
{"v":1,"type":"command","request_id":"bootNonce-1","command":"start","session_id":null}
```

`v` inteiro1, `request_id` de1–64 caracteres `[A-Za-z0-9_-]`, campos desconhecidos,
duplicados, JSON inválido e números não finitos rejeitados. `session_id` inteiro positivo
até2147483647 quando presente. Firmware usa nonce de boot128bits e contador; substituir
nonce somente em novo boot, nunca ao retransmitir o mesmo comando.

| Comando | Sessão/efeito |
|---|---|
| start | null; somente idle; cria uma sessão e abre microfone |
| pause | id atual; fecha stream, conserva áudio e confirma paused |
| resume | id atual; reabre stream antes de confirmar recording |
| finish | id atual; fecha captura, envia chunks e pede análise |
| retry | id anterior; após erro/conclusão cria nova sessão e captura |
| status | id atual, ou null para descoberta/idle; consulta, sem iniciar captura |

O touch mostra PENDING e bloqueia nova ativação comum até confirmação/timeout.
A ação RESEND é local ao controlador: retransmite exatamente a linha anterior,
inclusive request_id. Nova tentativa deliberada usa retry com novo request_id.

## Respostas

Confirmação de estado:

```json
{"v":1,"type":"state","request_id":"bootNonce-1","session_id":42,"state":"recording","is_demo":true}
```

`recording` só é emitido depois de o stream iniciar. `pause` espera paused, `resume`
espera recording, `finish` espera processing ou resultado/erro; resposta divergente
é erro recuperável, não confirmação. `state=idle` pode ter session_id null.

Resultado:

```json
{"v":1,"type":"result","request_id":"bootNonce-4","session_id":42,"state":"completed","is_demo":false,"asr_provider":"faster_whisper","topic_provider":"local_keywords","topics":["respiração celular"],"summary":"Assuntos identificados. Isso nao comprova acerto ou dominio."}
```

Este exemplo real documenta o candidato de extração, **não sua adoção**. Antes de enviar,
o bridge valida SessionDetail completed, id inteiro correto, texto não vazio, origem
executada e tópicos com session_id correto. Firmware exige tipo/estado/campos/limites,
sessão atual e solicitação esperada de finish/status (ou heartbeat durante processamento).
`is_demo` é booleano obrigatório; etapas mock não podem produzir resultado real.
Até8 tópicos, cada um até120 bytes UTF-8, resumo até240bytes, provedores até64bytes.
O bridge limita sem dividir caracteres. Lista vazia é válida: não inventar assuntos.
Resultado antigo, outra sessão, simples ACK ou statecompleted sem conteúdo não é sucesso.

Erro:

```json
{"v":1,"type":"error","request_id":"bootNonce-4","session_id":42,"state":"error","is_demo":false,"code":"audio_unusable","message":"Confira a captura e tente novamente."}
```

Erros anteriores à criação podem trazer session_id null. Código até64bytes, mensagem
até160bytes. Principais códigos do bridge: capture_failed, disconnected, interrupted,
backend_unavailable, invalid_result, request_conflict, invalid_state, invalid_command.
Erros de backend persistidos também chegam pelo código, por exemplo audio_unusable.
O display recebe estado textual, modo, resumo e tópicos em uma view independente do driver.

## Prazos, retransmissão e recuperação

- ACK de comando:5s no firmware. HTTP comum:5s no bridge. Permissão/driver lentos
  podem exceder janela; isso vira timeout, não sucesso. Corrigir no Mac e reenviar/consultar.
- Heartbeat status a cada2s; ausência de resposta por8s indica desconexão. O bridge
  também encerra captura ao perder comandos válidos por8s. Processing continua localmente.
- Resultado:120s de janela no firmware; HTTP finish aguarda até125s. Não é promessa de
  tempo de ASR. Timeout permite STATUS manual com nova janela, sem pedir nova análise.
  Heartbeats não estendem indefinidamente essa janela.
- Captura máxima30min/57,6MB PCM; atingir limite é erro, não nota sobre o estudante.
- Reconexão serial: tentativa a cada1s; leitura0,1s, escrita2s, sem flush bloqueante.

O journal SQLite grava intenção antes do efeito e conserva recibos. Mesmo id/payload
retorna estado atual; mesmo id/payload diferente é conflito. Reenvio antigo não reabre
microfone. Início concorrente usa unicidade backend; finalização usa claim atômico.
Após reinício incerto não há captura automática. Se a resposta de finish se perder,
GET/status recupera o resultado persistido; backend não analisa novamente a sessão.

Sem seleção dos drivers touch/display/RX serial, o firmware retorna indisponibilidade
na inicialização. A experiência física de mesa deve seguir o [roteiro manual](manual-validation.md).
