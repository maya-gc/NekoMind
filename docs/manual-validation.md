# Validação na mesa — pendente de execução física

Este roteiro não é resultado de teste. A placa, o display touch, os controladores,
os pinos e as dimensões ainda não foram escolhidos. Não há evidência física de
firmware, touch, microfone do Mac ou Whisper real nesta entrega automatizada.

## Preparação

1. Selecionar placa ESP32, display touch e drivers compatíveis; implementar os
   hooks de placa documentados no firmware. Compilar com ESP-IDF para o alvo
   escolhido, revisar pinos e tensão antes de conectar.
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
tópicos e reenvio com uma mão. Ajustar layout depois de escolher o display.

Registrar data, responsável, passos, esperado/observado e limitações. Teste com
microfone/serial/modelo substituto não marca nenhum item físico como aprovado.
