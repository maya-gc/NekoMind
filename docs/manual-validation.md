# Validação na mesa

Em 21/09/2026, a unidade USB foi identificada como ESP32-S3 com LCD ILI9341
240×320 e touch XPT2046. O [driver e pinagem deste protótipo](esp32-s3-display-touch.md)
foram exercitados na bancada. Com backend em demo, a pessoa confirmou gatinho
estável, diagnóstico, início, pausa, retomada, finalização, resultado demonstrativo
e nova tentativa. O backend persistiu áudio do microfone do Mac e um resultado
`is_demo=true`, `asr_provider_used=mock` e `topic_provider_used=mock` nesse ensaio.

Também em 21/09/2026, a unidade conectada passou por uma sessão real de voz humana:
Diagnóstico → Pronto → Começar → Finalizar → conclusão no LCD. O SQLite confirmou
`is_demo=false`, `capture_source=mac_microphone`, ASR `faster_whisper`, extração
`local_keywords`, `analysis_origin=real` e estado `completed`, sem código de erro.
O WebRTC VAD registrou 22,32 s de fala detectada em 25,98 s de áudio. O painel
`/public` exibiu as quatro etapas concluídas, tempo de captura, contagem de palavras
e termos reconhecidos, sem expor a transcrição completa. Esta é evidência do
percurso funcional, não uma medição de precisão ou uma calibração acústica completa.
O [roteiro de apresentação](day-of-rehearsal.md) registra a configuração local.

## Preparação

1. Conferir ligações 3V3 e GPIOs contra o protótipo documentado; compilar e gravar
   o firmware ESP-IDF para esp32s3. Observar rosto, rótulos e contraste no LCD.
   Calibrar o touch localmente e confirmar que cada botão responde na área correta.
2. Configurar o backend e o bridge no Mac em loopback. Modo demo é explicitamente
   demonstrativo; modo real exige modelo local e dependências indicadas.
3. Em Ajustes do Sistema → Privacidade e Segurança → Microfone, permitir captura
   ao aplicativo que executa o Python/terminal quando o macOS solicitar. Não
   assumir que permissão do navegador autoriza o processo local.
4. Abrir a porta USB correta (somente um processo). Manter o Mac ligado, com tampa
   aberta e sem suspensão. Verificar o indicador de modo no gatinho.

## Fluxo touch (sem tocar na tela do Mac após inicialização)

- Tocar começar duas vezes rapidamente. Deve haver um comando pendente, uma sessão
  e uma captura; só mostrar gravando após a confirmação do Mac.
- Explicar um assunto por 20–60 segundos, fazer pausas de raciocínio longas. Não
  deve haver encerramento automático por silêncio.
- Pausar no touch; conferir que o microfone parou e que fala durante a pausa não
  aparece no WAV/transcrição. Retomar e confirmar nova captura antes de gravando.
- Finalizar. O microfone para, o avatar mostra processamento, e somente um resultado
  validado da sessão atual leva à conclusão. Conferir tópicos e identificação demo/real.
- Perder deliberadamente uma confirmação por ferramenta de teste e reenviar o mesmo
  pedido. Conferir uma sessão/captura/análise e registros sem duplicação.
- Repetir a finalização e consultar o resultado. Deve retornar o mesmo resultado.
- Tentar novamente cria uma nova sessão, preservando a anterior.

## Falhas e recuperação

- Negar permissão ou escolher dispositivo inválido: mostrar erro de captura, nunca
  gravando. Corrigir no Mac e tentar novamente pelo touch.
- Desconectar USB durante captura e durante processamento; confirmar encerramento
  da captura quando desconectado e ausência de conclusão fictícia. Reconectar e
  consultar estado. Resultado atrasado de outra sessão deve ser ignorado.
- Parar o bridge e reiniciá-lo; nunca reiniciar microfone automaticamente. Um pedido
  retransmitido não deve abrir uma segunda captura após reinício incerto.
- Tornar backend/modelo indisponível: erro explícito, sem mock. Se processamento
  exceder espera, consultar o estado até conclusão real ou erro, sem disparar outra análise.
- Enviar silêncio, áudio vazio, WAV inválido, ruído de ventilador, teclado e música.
  O detector é imperfeito: registrar falsos positivos/negativos e ajustar com evidência.
  Falha de captação não pode gerar nota de conhecimento.

## Qualidade acústica e acessibilidade

Registrar chip/RAM/macOS, microfone/dispositivo, distância (mesma mesa), ambiente,
modelo/device/compute_type e parâmetros VAD. Testar voz normal e baixa, sotaques,
pausas e temas distintos. Comparar transcrição com a fala por avaliação local
consentida; não versionar áudio/transcrição. Verificar tamanho e separação dos
controles, contraste, rótulos textuais de estado, modo demo persistente, leitura dos
tópicos e reenvio com uma mão. Ajustar layout conforme a observação no display.

Registrar data, responsável, passos, esperado/observado e limitações. Teste com
microfone/serial/modelo substituto não marca nenhum item físico como aprovado.
# Ensaio adicional — conteúdo guiado opcional (NM-020 a NM-025)

Com backend real, bridge e ESP32-S3 já ligados, confirmar o token no painel
`/presenter`. Cadastrar dois textos curtos e distintos (por exemplo ciclo da
água e fotossíntese), cada um em dois ou três parágrafos. Revisar os pontos
derivados, salvar e selecionar o primeiro. Esperar a seleção aparecer no
painel, tocar **Começar** no LCD e explicar o conteúdo pelo microfone do Mac.
Enquanto fala, observar a sinalização provisória no painel e a expressão/texto
da gatinha. Pausar por alguns segundos: nenhum novo parcial deve ser emitido;
retomar. Finalizar: conferir relatório persistido, pontos/evidências/origem,
resultado breve no LCD e ausência da transcrição completa no painel público.

Repetir com fala fora do assunto, voz baixa, ruído e silêncio; áudio ruim não
pode causar carinha triste nem nota pedagógica. Testar toque duplo, reenvio de
finish, reset e perda temporária da USB. Editar/excluir o conteúdo original e
confirmar que o relatório e a versão da sessão anterior continuam acessíveis.
Voltar a **Modo livre** e repetir um fluxo real e um demo: visual/resultado
antigos devem permanecer. Medir com cronômetro: intervalo e latência dos
parciais, taxa de frames, tempo entre finalizar e resultado, CPU/memória do
Mac. Anotar hardware/modelo/ambiente; o ensaio com fala sintetizada em
[conteúdo guiado](guided-content.md) não substitui esta validação física.
