# Status NekoMind — 11/09/2026

## Resumo executivo

O MVP touch + Mac está implementado, testado em software e publicado na branch
[`feat/nekomind-touch-mac-mvp`](https://github.com/maya-gc/NekoMind/tree/feat/nekomind-touch-mac-mvp).
O código funcional mais recente desta rodada é
[`6e2291ecaf01a96d6820745c87bff27fd590eb90`](https://github.com/maya-gc/NekoMind/commit/6e2291ecaf01a96d6820745c87bff27fd590eb90).
A `main` permaneceu inalterada.

O estudante controla a sessão pelo touch; o Mac captura o microfone, valida a presença
de fala, transcreve, extrai termos, persiste a sessão e devolve apenas o resultado
correlacionado. O display do gatinho concentra rosto, estado, controles e conclusão
compacta. O painel público do Mac mostra a jornada técnica para a plateia.

## Melhorias entregues

| Item | Status para acompanhamento |
|---|---|
| NM-001 — Confirmação real | Conclusão somente após resultado `completed` válido da sessão atual. Mensagem antiga, inválida, de erro ou de outra sessão não produz sucesso. Timeout, desconexão e recuperação possuem estados próprios. |
| NM-002 — Cache ASR | Faster-whisper carrega de forma lazy e é reutilizado por modelo, dispositivo e `compute_type`. Inicialização e consumo do gerador são protegidos; falha não deixa cache inválido; cleanup ocorre no encerramento. |
| NM-003 — Touch + microfone Mac | Iniciar, pausar, retomar, finalizar e tentar novamente passam pelo bridge do Mac. O estado gravando aparece depois da abertura efetiva do stream. Pausa fecha a captura e retomada reabre. |
| NM-004 — Real x demo | Provedores desconhecidos ou indisponíveis falham explicitamente. Origem de ASR e extração é persistida e exibida. Qualquer etapa mock identifica o resultado como demonstração. |
| NM-005 — Fala utilizável | WAV é validado antes da análise. WebRTC VAD verifica presença de fala; nível e clipping complementam o diagnóstico. Silêncio, ruído e arquivo inválido não geram avaliação pedagógica. |
| NM-006 — Idempotência | `request_id`, `session_id`, recibos persistentes, transações e fila pendente impedem sessões, capturas, análises, tópicos e métricas duplicados. Nova tentativa deliberada recebe nova identidade. |
| NM-007 — Assuntos reais | Extrator lexical local usa somente texto presente na transcrição. Remove preenchimentos, candidatos fracos e duplicatas, limita o resultado visual e aceita lista vazia sem inventar tópicos. |
| NM-008 — Autoteste | Diagnóstico assíncrono verifica backend, bridge, microfone e dependências aplicáveis antes da sessão. Falhas levam a orientação e nova tentativa. |
| NM-009 — Recuperação | Manifesto, chunks e cursores são persistidos. Reinício durante captura entra em recuperação e nunca reabre o microfone sozinho. |
| NM-010 — Privacidade | Retenção de áudio é configurável e desativada por padrão. Exclusão confirmada limpa arquivos, transcrição, tópicos e métricas; tombstones permitem retomar limpeza parcial com segurança. |
| NM-011 — Histórico | Assunto pode ser confirmado/corrigido. Sessões concluídas preservam `ended_at`, versão das métricas e histórico local. Tendências continuam identificadas como heurísticas. |
| NM-012 — Calibração | Calibração curta registra identidade do microfone, avalia nível/clipping e descarta a amostra. O diretório é criado no primeiro uso e a janela configurada é respeitada. |
| NM-013 — Modo feira | Experiência local possui geração, reinício, projeção e limpeza controlados. Interface evita sucesso fictício e mantém recuperação acessível. |
| NM-014 — Avatar | Gatinho original reage aos estados pronto, gravando, pausado, processando, concluído e erro. Sinais textuais e redução de movimento complementam cor/animação. |
| NM-015 — Feedback de captação | Nível e clipping do Mac chegam ao protocolo com telemetria limitada. Avisos orientam melhorar captação sem transformar voz baixa em nota de conhecimento. |
| NM-016 — Jornada | Captura, transcrição, tópicos e persistência possuem eventos, durações e origens reais. A interface não inventa porcentagem de progresso. |
| NM-017 — Painel público | `/public` é somente leitura e mostra funcionamento, estado, jornada e termos para a plateia, sem transcrição integral nem comandos administrativos. |
| NM-018 — Resultado no touch | Resultado da feira foi reduzido de até onze cartões para dois: prova de processamento e termos reconhecidos. Layouts 240×320 e 320×240 foram verificados sem sobreposição. |
| NM-019 — Painel do apresentador | `/presenter` usa token local em memória para diagnóstico, modo, assunto, histórico, recuperação, cancelamento, exclusão e reset. |

## Ajustes realizados durante os testes

- Corrigir calibração que aguardava apenas 100 ms e falhava sem diretório de captura.
- Garantir que a pausa não acrescente bytes e explicar na tela como retomar.
- Persistir e exibir corretamente a data final `ended_at` no histórico.
- Validar o token antes dos comandos e iniciar automaticamente o diagnóstico real.
- Colocar erro de token dentro do diálogo, sem cobrir a área principal ou os botões.
- Distinguir recuperação ainda não consultada de ausência confirmada de recuperação.
- Substituir confirmação nativa bloqueante por diálogo acessível na página.
- Corrigir overflow, botão Pausar cortado, resumo sobre a navegação e paginação
  em 240×320, 320×240 e 1440×900.
- Trocar resumo de conversa aleatória por evidências objetivas da execução.
- Exibir `Termos reconhecidos pelo NekoMind` para não atribuir ao usuário um erro do ASR.
- Filtrar termos conversacionais genéricos, duplicatas contidas e candidatos fracos.
- Identificar corretamente o modo real no bridge e impedir que demo pareça processamento real.

## Validação executada

| Grupo | Resultado |
|---|---|
| Backend Python | 184/184 aprovados |
| Ciclo de vida ASR | 10/10 aprovados com modelo substituto |
| Frontend web | 28/28 aprovados |
| Streamlit | 6/6 aprovados |
| Firmware portátil | 22 casos C aprovados com warnings tratados como erro |
| Browser | Viewports 240×320, 320×240 e 1440×900; gate de evidência 11/11 |
| Assets | Gate 5/5 |
| Execução local real | Microfone/PortAudio, WebRTC VAD, faster-whisper tiny, `local_keywords`, persistência e limpeza de áudio exercitados com voz sintetizada local |

## Limites e próximos passos

- Validar fala humana e calibrar o microfone no ambiente real da apresentação.
- Identificar placa ESP32, controlador touch, pinos, tensão e orientação do módulo.
- Implementar/conectar drivers específicos, compilar com ESP-IDF, gravar a placa e
  testar touch, TFT e USB/serial físicos.
- Medir primeira transcrição, transcrições seguintes, memória, latência serial,
  FPS e consumo do display no hardware escolhido.
- Avaliar modelo de ASR melhor que `tiny` para a apresentação; o ensaio atual mostrou
  que termos reconhecidos podem divergir da frase reproduzida.
- Manter Mac ligado, tampa aberta, sem suspensão e com permissão de microfone durante
  a sessão. Não expor backend, token, áudio ou transcrição em rede pública.
- **Incidente de dados já registrado:** durante uma revisão anterior, o banco local
  padrão foi recriado indevidamente. O conteúdo anterior não foi recuperado; a cópia
  pós-incidente foi preservada, e uma restauração adicional depende de backup externo.
  O incidente e as medidas posteriores estão detalhados no [relatório de QA](qa-report.md).

O software está pronto para revisão e demonstração local no emulador. A integração
física completa depende das decisões e testes de hardware listados acima.
