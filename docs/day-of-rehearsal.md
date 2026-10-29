# Ensaio local para apresentação

Este roteiro usa o ESP32-S3/ILI9341/XPT2046 já montado, o microfone do Mac e
processamento **local**. A sessão real foi exercitada nessa unidade em 21/09/2026.
Não é um serviço implantado na internet: o Mac deve ficar ligado, com backend e
bridge ativos, durante toda a apresentação. O LCD é a interface da pessoa; o Mac
mostra o painel público em `http://127.0.0.1:8000/public`.

## Antes de abrir a sala

1. Conectar o ESP32 por USB e confirmar que o gatinho e os botões aparecem estáveis.
   A calibração do touch já foi gravada no NVS da unidade testada. Confirmar a porta
   com `backend/.venv/bin/python -m serial.tools.list_ports`; no ensaio ela foi
   `/dev/cu.usbmodem101`, mas pode mudar após reconexão. Fechar monitor serial e
   qualquer outro processo que use essa porta.
   Tocar **ESCURO/CLARO** no canto superior direito para escolher a paleta do LCD;
   conferir legibilidade dos botões e que a escolha permanece após RST/EN.
2. Confirmar as dependências de `backend/requirements-mac.txt` e
   `backend/requirements-real.txt`. O modelo usado neste Mac é o snapshot público
   `Systran/faster-whisper-small`, revisão
   `536b0662742c02347bc0e980a01041f333bce120`, armazenado em
   `backend/storage/models/faster-whisper-small/`. Ele foi baixado antes do ensaio;
   o backend usa `local_files_only=True` e não o baixa durante a apresentação.
3. Configurar `backend/.env` local, ignorado pelo Git, com as linhas abaixo. Trocar
   o caminho pelo diretório absoluto do modelo neste Mac. Não copiar o arquivo nem
   áudio ou banco para o Git.

   ```dotenv
   NEKOMIND_MODE=real
   NEKOMIND_ASR_PROVIDER=faster_whisper
   NEKOMIND_ASR_MODEL_SIZE=/caminho/absoluto/NekoMind/backend/storage/models/faster-whisper-small
   NEKOMIND_ASR_DEVICE=cpu
   NEKOMIND_ASR_COMPUTE_TYPE=int8
   NEKOMIND_LLM_PROVIDER=local_keywords
   NEKOMIND_RETAIN_RAW_AUDIO=false
   ```

4. Em um terminal na raiz do repositório, iniciar `bash scripts/run_backend.sh`.
   Em outro, iniciar o bridge com:

   ```bash
   cd backend
   .venv/bin/python -m app.mac --port /dev/cu.usbmodem101
   ```

   O bridge mantém o Mac acordado via `caffeinate`; manter a tampa aberta e o Mac
   na energia. Somente um backend e um bridge devem usar o banco/serial. Se o macOS
   solicitar, autorizar o microfone para o aplicativo de terminal em Ajustes do
   Sistema → Privacidade e Segurança → Microfone. Permissão do navegador não autoriza
   o capturador local.
5. Abrir `http://127.0.0.1:8000/public` no Mac e projetar essa janela. É somente
   leitura, sem token. A página `/touch` é um emulador para teste do operador; no
   ensaio com o ESP32, usar os botões físicos do LCD. Confirmar o selo **REAL** no
   painel e no dispositivo; se aparecer **DEMO**, conferir `backend/.env` e reiniciar
   backend/bridge antes de apresentar. Não colocar token em URL ou projeção.

## Fluxo que a plateia verá

1. No gatinho, tocar **Diagnóstico**. Esperar **Verificando** e depois **Pronto**.
   Se houver erro, corrigir microfone, modelo, backend ou USB antes de começar.
   **Pronto** permanece enquanto a pessoa lê as instruções; o reset automático de
   feira não deve cancelar a preparação antes de **Começar**.
2. Tocar **Começar**. Apenas após a confirmação do Mac o LCD mostra **Ouvindo**.
   Falar por 20–30 segundos sobre um assunto simples. O microfone é o do Mac; não
   há captura no ESP nem no navegador. Pode-se pausar e retomar pelo LCD. Pausa
   interrompe a captura e não encerra a sessão por silêncio de raciocínio.
3. Tocar **Finalizar**. O LCD mostra processamento e depois a confirmação de fala
   capturada e processada. Os cartões do resultado mostram até alguns termos
   reconhecidos; **Encerrar** volta ao início e **Nova tentativa** cria outra
   sessão. Não tratar os termos como nota ou prova de domínio.
4. No Mac, o painel público acompanha Captura → Transcrição → Tópicos → Resultado,
   com origem das etapas, duração, contagem de palavras e termos reconhecidos.
   A transcrição completa fica fora da projeção. O resultado deve indicar **REAL**.

## Se algo falhar

- **USB indisponível / timeout do Mac:** conferir cabo, porta e se o bridge ainda
  roda. Reiniciar o bridge e tocar Diagnóstico; não iniciar outro bridge na mesma
  porta. Após reconexão, usar recuperação/nova tentativa conforme o LCD.
- **Permissão ou dispositivo do microfone:** abrir as permissões do terminal no
  macOS, verificar o dispositivo de entrada e refazer Diagnóstico. Se a decisão
  já foi concedida, o macOS não mostra o aviso novamente.
- **Modelo ou análise indisponível:** verificar caminho absoluto e modo no `.env`,
  reiniciar backend e bridge. Não trocar silenciosamente para mock.
- **Sem fala detectável / captação fraca:** aproximar-se do microfone e tentar de
  novo. O sistema não deve atribuir nota ruim a uma falha de captura.
- **Painel não abre:** `http://127.0.0.1:8000/public` só funciona no Mac com o
  backend ativo; conferir `curl -I http://127.0.0.1:8000/public` no próprio Mac.

O ensaio real de 21/09 comprovou uma sessão completa, sem avaliar estatisticamente
a qualidade do ASR ou do extrator. Antes de uma apresentação pública, repetir o
teste com a pessoa que vai falar, na posição real da mesa e no ruído do local.

Em 01/10, um novo teste na unidade conectada encontrou timeout ao tocar
**Começar** depois de **Pronto**. O histórico local mostrou que o reset automático
do modo feira havia voltado o Mac a `idle` antes do toque; o início foi recusado
sem criar sessão. Corrigimos o reset para atuar somente após conclusão, erro ou
recuperação. O firmware também passou a mostrar a resposta de erro correlacionada
à nova tentativa, em vez de descartá-la e terminar em timeout. Depois do build,
flash verificado e reinício do backend/bridge, a pessoa na bancada informou que
o fluxo funcionou. Isso confirma o teste manual relatado nessa unidade; não mede
precisão de transcrição nem cobre outros microfones ou ambientes.
# Roteiro alternativo: conteúdo guiado

Antes de abrir a bancada ao público, o operador escolhe no `/presenter` um
texto curto já revisado e confirma a seleção. A pessoa toca **Começar** no LCD
e explica o texto em voz alta. A gatinha mostra expressão e texto de aderência
**provisórios**, enquanto a tela do Mac mostra a jornada e um percentual
compacto, sem expor a transcrição parcial. **Finalizar** produz o relatório
somente após áudio/fala/transcrição final válidos; a tela pública mostra pontos
mencionados/não mencionados com trechos curtos e o LCD um resumo. Dizer ao
público que isso demonstra batimento com o texto, não avaliação de conhecimento.

Se o batimento ao vivo estiver indisponível, continuar a captura e observar o
aviso; não atribuir erro ao visitante. Se o modelo ASR não estiver pronto,
voltar ao modo livre/demo identificado, sem simular resultado real. Para testar
fala espontânea sem texto, selecionar **Modo livre** antes da próxima sessão.
Não mudar a seleção durante uma sessão em andamento.

Para um briefing novo, o painel do Mac agora mostra só **1. Adicione o contexto**
e **2. Confira e use**. Cole texto e toque **Analisar briefing com IA local**,
ou escolha PDF/TXT/MD ou cole uma URL pública para iniciar a análise local após
o carregamento. Revise título, texto e pontos. Toque **Salvar e usar na próxima
sessão**; confira o nome no cartão **Próxima sessão** antes de chamar a pessoa ao
display. Histórico, modo feira/normal, diagnóstico e comandos de manutenção
ficam em **Ferramentas do operador**. PDF escaneado, URL que exige login ou
modelo Ollama indisponível podem exigir correção no Mac; não apresente uma
prévia sem pontos como análise concluída. A análise do briefing escolhe trechos
do material; o batimento com a fala continua lexical e não avalia domínio.
