# NekoMind — contexto para continuar o desenvolvimento

Atualizado em 29/10/2026. Este documento sintetiza as decisões deste chat e o
estado do código publicado. Não é uma transcrição integral da conversa nem substitui
um novo teste na máquina de quem vai desenvolver.

## Leia isto primeiro

- **Objetivo:** uma estação física de estudo em que a pessoa escolhe um ponto no
  touch da gatinha, explica em voz alta, recebe pergunta e dica, responde de novo
  e vê uma comparação limitada ao material preparado.
- **Arquitetura escolhida para o protótipo:** ESP32-S3 com LCD/touch faz a
  interação; o Mac captura pelo próprio microfone, processa tudo localmente e
  reproduz a voz pelo próprio alto-falante. A ligação é USB/serial. O Mac precisa
  ficar ligado durante a demonstração.
- **Não começar por `main`:** o estado atual está na branch
  [`codex/nekomind-current-snapshot`](https://github.com/maya-gc/NekoMind/tree/codex/nekomind-current-snapshot),
  aberta no [PR #1 em rascunho](https://github.com/maya-gc/NekoMind/pull/1).
  Em 29/10, `main` ainda não continha esse trabalho. O commit publicado é
  `268c876`; o conteúdo dos arquivos foi conferido contra a árvore local.
- **Fronteira pedagógica:** menção de palavras ou trechos do briefing não é
  correção factual, nota nem prova de domínio. A comparação atual é lexical e
  curta; conteúdos complexos exigem avaliação e possivelmente outra abordagem.
- **Fronteira acadêmica:** o pedido inicial mencionava microfone e alto-falante
  no dispositivo. Eles **não estão integrados ao firmware ativo**; o protótipo
  usa os do Mac. A rubrica oficial A3 e a aceitação dessa divisão ainda precisam
  ser confirmadas antes de declarar aderência ao edital.

## Como chegamos ao desenho atual

| Etapa | Decisão ou evidência |
| --- | --- |
| Análise do produto e A3 | Foram feitos estudos visuais em `output/pdf/`. A página do Notion foi tratada como contexto histórico, pois o próprio responsável avisou que ela não estava totalmente atualizada. A rubrica oficial A3 não foi comprovada no material consultado. |
| Hipótese B: toda a IA no ESP32-S3 | Foi estudada e depois descartada para o MVP conversacional. O laboratório em `experiments/esp32_s3_offline_lab/` verificou alocações em QEMU com PSRAM simulada, **sem rodar ASR, LLM ou TTS reais no ESP**. Os PDFs sobre a hipótese B são estudos históricos, não a arquitetura aprovada agora. |
| Foco de produto | Priorizar a interação com o estudante no touch: missão por ponto, pergunta com dica e segunda resposta, e conversa em voz alta. O modo livre permanece. |
| Voz | O responsável pediu português brasileiro, sem timbre robótico, local e gratuito. Depois de ouvir Kokoro e Chatterbox, escolheu **Kokoro pela rapidez**. O código usa `pf_dora` no Mac; não usa a voz oficial da Hatsune Miku. |
| Teste físico assistido | O responsável confirmou no ESP a tela de missões após reset, gravação iniciada por **Começar**, dica exibida, pergunta, segunda gravação, comparação exibida, retorno às missões e voz no Mac. Os relatos validam esse percurso naquela bancada, não todos os tipos de conteúdo ou ambientes. |

## Arquitetura em operação

```text
Pessoa -> ESP32-S3 / LCD ILI9341 240x320 / touch XPT2046
              | comandos, estados e resultado curto (JSON Lines, USB)
              v
       bridge local no Mac -> microfone do Mac -> FastAPI local
                                              -> faster-whisper (ASR pt)
                                              -> análise lexical / SQLite
              ^                               -> Ollama opcional no briefing
              | pergunta, dica e comparação
       Kokoro pt-BR -> alto-falante do Mac

       /presenter: preparo pelo operador
       /public: resultado para a plateia
       /touch: emulador de teste, não o hardware físico
```

O backend escuta `127.0.0.1:8000` com um worker. A serial transporta controle e
resultados, **não áudio**. Uma instância do bridge controla a captura. O token
local do operador é criado em `backend/storage/operator-token` e não deve ser
copiado para mensagens, URL ou Git. Áudio, banco, journal, `.env` e pesos dos
modelos ficam fora do repositório. A retenção de áudio bruto é desligada por
padrão. Consulte [arquitetura](architecture.md) e [protocolo](iot_protocol.md).

### Papéis dos modelos e serviços

| Componente | Uso atual | Limite |
| --- | --- | --- |
| `faster-whisper-small` | Transcrição local em português no Mac, com modelo baixado antes de rodar. | Acurácia varia com captação, ruído e voz; não é executado no ESP. |
| `local_keywords` | Extrai termos do que foi transcrito; funciona offline. | É regra lexical, não LLM ou avaliação de conhecimento. |
| Ollama `qwen2.5:3b` | Opcional para sugerir pontos literais de um briefing e relações tentativas entre fonte e fala. | Se faltar, a análise opcional indica indisponibilidade; o operador revisa os pontos. |
| Kokoro `pf_dora` | Fala local em pt-BR no alto-falante do Mac. Pesos são baixados uma vez. | Não há síntese no ESP; instalação e cache são necessários em outro Mac. |

Não há cobrança por chamada de API no fluxo escolhido. Isso não significa custo
zero de computador, hardware, energia ou tempo de preparação. Não assumir preços
dos PDFs como cotações atuais.

## O que o código faz hoje

1. Em `/presenter`, o operador prepara texto, TXT, MD, PDF com texto selecionável
   ou URL pública; revisa e salva os pontos para a **próxima** sessão. Importar ou
   analisar uma prévia, sozinho, não ativa o material. O modo livre segue como
   alternativa. PDF escaneado exige OCR externo; OCR não está integrado.
2. O touch recebe até 30 missões curtas. O estudante percorre os pontos e toca
   **Começar**. O Mac só abre o microfone após confirmação do comando.
3. **Finalizar** fecha a captura e produz transcrição e relatório final. Em sessão
   guiada real, aparece uma pergunta ligada a um ponto do material. **Pedir dica**
   apresenta e lê uma pista; **Responder** abre uma segunda captura associada à
   primeira. A gatinha lê perguntas, dicas e comparação pelo Mac quando Kokoro
   está ativo.
4. A comparação usa o mesmo ponto da pergunta, estados de cobertura e pequenos
   trechos presentes na fonte e na fala. Cada tentativa é uma sessão no backend;
   o journal do bridge preserva o vínculo e permite recuperar o estado após
   reinício sem reabrir o microfone sozinho.
5. `/public` mostra a jornada e evidências compactas sem a transcrição completa.
   O modo **DEMO** é identificado; silêncio ou dados simulados não devem aparecer
   como resultado **REAL**.

**Cuidado ao evoluir:** `backend/app/mac/dialogue.py` limita a comparação a 94
bytes UTF-8 e produz mensagens por coincidência lexical. Para pontos longos, a
pergunta pode se tornar genérica. A função `choose_focus` atualmente prefere a
missão selecionada quando ela existe, enquanto a descrição em
[interactive-dialogue.md](interactive-dialogue.md) fala em escolher o ponto menos
mencionado. Conferir e alinhar regra de produto, implementação e documentação.
O responsável observou uma comparação inicialmente confusa e pediu adaptação
para perguntas difíceis, como mecânica quântica. Uma frase mais clara foi vista
no display depois da correção, mas **generalização semântica não foi validada**.

## Mapa rápido do repositório

| Caminho | Responsabilidade |
| --- | --- |
| `backend/app/api/`, `services/`, `database/` | API, sessões, conteúdo, batimento, transcrição, SQLite e retenção. |
| `backend/app/mac/bridge.py`, `capture.py`, `dialogue.py`, `speaker.py` | USB, microfone, fluxo de duas respostas, recuperação e Kokoro. |
| `frontend/web/` | `/presenter`, `/public` e emulador `/touch`. |
| `iot/nekomind_firmware/main/` | Controlador, protocolo, layout, SPI, display e touch do ESP32-S3. |
| `frontend/streamlit/` | Histórico e consulta; não grava áudio. |
| `docs/interactive-dialogue.md`, `docs/guided-content.md` | Contrato da experiência e limites da análise. |
| `output/pdf/`, `experiments/` | Estudos de produto/arquitetura e ensaios históricos. |

## Evidência e limites dos testes

- Em 21/09 houve uma sessão real com fala humana no ESP/USB/Mac, documentada em
  [day-of-rehearsal.md](day-of-rehearsal.md). Em 01/10, um timeout após **Pronto**
  foi corrigido e o fluxo voltou a funcionar no display segundo o teste de
  bancada. Esses registros são anteriores ao diálogo de duas respostas.
- Na rodada mais recente deste chat, o responsável confirmou fisicamente as
  missões, a pergunta, a dica, a segunda gravação, a comparação, o diagnóstico e
  a voz. A mensagem vista ao fim foi do tipo: “Na segunda, faltou Sol aquece a
  água; antes apareceu.” Isso confirma a exibição dessa frase específica.
- Em 26/10, passaram **24 testes direcionados do backend** e **40 testes Node do
  frontend**. Não representar essas contagens como execução integral de todas
  as suítes. O build completo do firmware não terminou naquela rodada porque o
  ambiente ESP-IDF não estava carregado; builds e flashes tinham passado antes.
- O laboratório da hipótese B só mediu reservas de memória no QEMU. Não usar
  esses números como benchmark de IA ou prova de autonomia do ESP.
- Faltam ensaios repetidos com estudantes, ruído real, diferentes sotaques,
  conteúdo longo/complexo, latência ponta a ponta, legibilidade do display e
  confiabilidade da voz na sala.

## Preparar outra máquina para desenvolver ou testar

Trabalhar a partir da branch publicada, em branch própria para as mudanças:

```bash
git clone --branch codex/nekomind-current-snapshot \
  https://github.com/maya-gc/NekoMind.git
cd NekoMind
git switch -c codex/minha-contribuicao
PYTHON_BIN=python3.12 bash scripts/setup_backend.sh
backend/.venv/bin/python -m pip install -r backend/requirements-mac.txt
backend/.venv/bin/python -m pip install -r backend/requirements-real.txt
cp -n backend/.env.example backend/.env
```

Para enviar commits ao repositório original, o colaborador precisa de acesso de
escrita; sem ele, pode trabalhar em um fork e abrir um PR. A branch acima serve
de ponto de partida, não deve ser substituída pelo `main` antigo.

Para modo **REAL**, configurar localmente `backend/.env` com
`NEKOMIND_MODE=real`, `NEKOMIND_ASR_PROVIDER=faster_whisper`, caminho absoluto
do modelo ASR já baixado em `NEKOMIND_ASR_MODEL_SIZE`, `cpu`/`int8` e
`NEKOMIND_LLM_PROVIDER=local_keywords`. Se quiser os briefings por IA local,
instalar Ollama e preparar o modelo configurado em `NEKOMIND_BRIEFING_MODEL`.
Para a voz escolhida, instalar `espeak-ng`, executar
`bash scripts/setup_voice_mac.sh` e ativar `NEKOMIND_TTS_PROVIDER=kokoro` ou
passar `--voice kokoro` ao bridge. Preparar os pesos antes de exigir execução
offline. [backend/README.md](../backend/README.md) contém os detalhes.

Com o ESP conectado por USB, descobrir a porta em vez de copiar uma porta antiga:

```bash
backend/.venv/bin/python -m serial.tools.list_ports
bash scripts/run_backend.sh
# Em outro terminal:
cd backend
.venv/bin/python -m app.mac --port /dev/cu.PORTA_DO_ESP --voice kokoro
```

Abrir `http://127.0.0.1:8000/presenter` para o operador,
`http://127.0.0.1:8000/public` para a plateia e `/touch` para emulação. O token
local é lido do arquivo criado pelo backend e usado somente no painel privado;
cada pessoa gera o seu próprio. Fechar qualquer monitor serial antes do bridge.
Para gravar firmware novo, seguir [pinagem e ESP-IDF](esp32-s3-display-touch.md)
e confirmar a porta. A calibração do touch fica no NVS; não apagar NVS como
primeira medida de recuperação.

### Roteiro mínimo de verificação

1. Rodar testes: `cd backend && .venv/bin/python -m pytest -q`; depois, da raiz,
   `node --test frontend/tests/*.test.mjs` e
   `bash iot/nekomind_firmware/scripts/test_firmware.sh`.
2. Em `/presenter`, preparar um texto curto com dois pontos distintos e confirmar
   **Salvar e usar na próxima sessão**. Conferir modo **REAL**.
3. No ESP, tocar **Diagnóstico**, aguardar **Pronto**, escolher missão, tocar
   **Começar**, falar e **Finalizar**. Confirmar pergunta no display.
4. Tocar **Pedir dica** e **Responder**; falar de novo e **Finalizar**. Conferir
   comparação no display, fala no Mac e vínculo das duas tentativas.
5. Repetir com uma explicação complexa, resposta sem menção, resposta parcial,
   inversão explícita, ruído e pausa. Registrar o que a interface realmente diz;
   não inferir acerto pedagógico a partir de cobertura lexical.

## Próximas decisões e pendências

1. **A3:** obter o edital/rubrica oficial e decidir como cumprir microfone e
   alto-falante exigidos. Hoje estão no Mac. Verificar também se o Mac pode ser
   usado na apresentação. Nenhum documento deste repositório prova a aderência
   formal.
2. **Pergunta/comparação:** definir comportamento pedagógico para pontos longos
   e conceitos complexos, esclarecer o foco da missão e testar mensagens com
   pessoas. A regra lexical atual não julga raciocínio científico.
3. **Bancada:** medir ASR, TTS e resposta ponta a ponta com o hardware montado,
   vozes e ruído reais; verificar contraste, toque e recuperação após USB/reset.
4. **Produto:** validar com estudantes e docentes se o objeto físico melhora a
   experiência frente a um app. Não há evidência de ganho educacional nem de
   viabilidade comercial estabelecida.
5. **Git:** o histórico de commits do checkout original está parcialmente preso
   em objetos do Git sem dados locais no iCloud. A branch do PR publica o
   **estado atual dos arquivos em um commit único**, não todo o histórico. Para
   colaborar agora, usar essa branch; não tentar reconstruir a história a partir
   do `main` antigo.

## Como compartilhar este contexto

Envie ao colaborador **este arquivo**, o [PR #1](https://github.com/maya-gc/NekoMind/pull/1)
e, se quiser mostrar o caminho das decisões, o link compartilhado do chat em
mensagem separada. O link do chat é uma captura para leitura; não concede acesso
ao checkout, ao ESP, aos modelos nem ao token. Como o repositório é público,
o link do chat não foi colocado aqui para não publicar a conversa inteira.
Se ele usar outra conversa com uma IA para desenvolver, pode começar com:
“Abra a branch `codex/nekomind-current-snapshot`, leia
`docs/handoff-colaborador.md` e `docs/interactive-dialogue.md`, confira o código
e os testes antes de propor alterações; trate a aderência ao edital A3 e a
avaliação semântica como pendentes.”
