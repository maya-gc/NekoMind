# Conteúdo guiado opcional (NM-020 a NM-025)

O modo livre continua padrão. No painel `/presenter`, o operador cadastra um texto
local, revisa os pontos-chave, seleciona o conteúdo da próxima sessão e espera a
confirmação da seleção antes de tocar **Começar** no LCD. Arquivos `.txt` e `.md`
são lidos pelo navegador **apenas no painel do operador** e enviados ao backend
local autenticado; o navegador não grava áudio. Ao selecionar **Modo livre**,
nenhum serviço de transcrição parcial ou batimento é iniciado.

O painel também importa PDF com camada de texto. Envia até 5 MB ao endpoint local
autenticado `POST /api/v1/contents/import-pdf`; o backend lê até 20 páginas com
`pypdf`, extrai até 50 mil caracteres e devolve texto e até oito frases candidatas
como prévia editável. A importação **não salva nem seleciona** o conteúdo. O
operador revisa texto/pontos, toca **Salvar e usar na próxima sessão** antes
da próxima sessão. O PDF bruto não é persistido. Arquivo inválido, protegido por
senha, longo demais ou digitalização sem texto selecionável gera erro claro;
OCR local ainda não foi implementado. Os pontos por frase são uma sugestão
lexical, não um resumo inteligente ou garantia de qualidade pedagógica.

## Preparo rápido do briefing

O `/presenter` apresenta duas etapas visíveis: trazer texto/PDF/TXT/MD/URL e
conferir título/pontos antes de salvar e aplicar à próxima sessão. Biblioteca,
histórico, diagnóstico e comandos de manutenção ficam recolhidos. Durante a
digitação, a atualização periódica do estado não recria o formulário nem perde
o foco. A URL pública é buscada pelo backend com limite de 1 MB e tempo de
conexão de 5 s; só HTML e texto são aceitos. Cada DNS e redirecionamento é
validado e a conexão é fixada ao IP público validado, com TLS verificado pelo
nome original. O site recebe uma requisição normal; URL e PDF bruto não são
persistidos. Não há suporte garantido a sites que exigem login, JavaScript ou
paywall. O texto retornado é sempre revisável antes de ser usado.
Em páginas da Wikipédia, o importador usa o corpo do artigo e ignora menus,
caixas de navegação, fórmulas renderizadas e referências finais. Em sites sem
estrutura de artigo reconhecível, a prévia pode conter ruído; revise antes de salvar.

O botão **Analisar briefing com IA local** usa Ollama em `127.0.0.1` e o modelo
`NEKOMIND_BRIEFING_MODEL` (padrão `qwen2.5:3b`). O modelo seleciona índices de
frases do próprio material; o backend valida tipo, faixa, unicidade e quantidade
antes de devolver até oito pontos literais. Não há fallback silencioso para
heurística quando Ollama está indisponível ou responde mal. Para textos longos,
o texto completo continua na prévia, mas a IA recebe até 24 frases literais
distribuídas pelo documento, limitadas a 12 mil caracteres. A interface avisa
quando houve amostragem; revise os pontos, pois partes não amostradas não são
analisadas pela IA. Após PDF/TXT/MD/URL, a análise local é iniciada automaticamente;
para texto colado, há botão explícito. Se a IA falhar, a prévia do texto continua
editável e os pontos ficam vazios para impedir confusão com resultado de IA.
Nenhum texto é enviado à nuvem.
Esses pontos representam o material, não verificação factual nem domínio da fala.

O conteúdo tem título, idioma `pt`, origem (`typed`, `txt`, `md`, `pdf`), versão e até 30
pontos de até 500 caracteres. Por padrão cada linha não vazia, inclusive item de lista, vira
um ponto. A edição manual pode combinar termos presentes no texto, mas não
introduzir termos alheios. A sessão conserva uma cópia exata do texto, pontos e
versão; editar ou excluir a biblioteca não reescreve sessões anteriores. Excluir
a sessão remove essa cópia e o relatório pelo fluxo de retenção existente. A
seleção usa `PUT` idempotente e é bloqueada durante captura ou análise.

Em sessão real guiada, o callback do microfone duplica os mesmos chunks PCM para
uma fila limitada e não bloqueante. Um worker transcreve janelas de até 12 s em
intervalos mínimos de 6 s com o mesmo faster-whisper local/cache. Quando a fila
enche, o worker descarta áudio antigo do canal **provisório**; o caminho de
captura oficial não usa essa fila. Parciais não vão ao SQLite, log, serial nem
painel público. Pausa, finalização, cancelamento e desconexão param o worker.
O ASR nativo já em execução não pode ser interrompido no meio da chamada; por
isso o tempo até a análise final precisa ser medido no Mac da apresentação.

O batimento `lexical-pt-v1` normaliza acentos/caixa, remove palavras comuns e
reduz sufixos portugueses simples. Sinônimos só são considerados quando o próprio
texto explicita um par de **uma palavra** entre parênteses, por exemplo
`evaporação (vaporização)`. Para cada ponto, escolhe a frase transcrita com mais
termos em comum. `covered` exige ≥70% dos termos e pelo menos dois termos distintos
(ou o único termo de um ponto de uma palavra); `partial` exige dois termos;
caso contrário `not_mentioned`. `possible_divergence` exige ≥70% de sobreposição
e inversão explícita da presença de `não/nao/nunca` na mesma frase. Isso é um
**sinal conservador**, não uma verificação semântica/factual. O modelo semântico
para **comparar fala e conteúdo** permanece futuro; Ollama nesta versão apenas
escolhe trechos do material para o briefing, sem avaliar a fala. Não há serviço
de IA remoto ativado.

O limiar de 70% exige a maioria forte dos termos; dois termos evitam que uma
palavra genérica marque um ponto longo. São parâmetros iniciais conservadores,
não calibrados com estudantes. A janela de 6 s reduz chamadas caras ao ASR e
mudanças a cada palavra; os 30 s antes da expressão preocupada permitem uma
introdução ou pausa de raciocínio. Voz baixa/clipping suspende essa reação.
Esses valores precisam ser recalibrados com o microfone e o público da feira.

O relatório usa somente a transcrição **final** validada. Traz lista de pontos,
evidência curta, estado, origem real/demo, cobertura e ordem/tempo **estimados**
pela posição do trecho no texto em relação à duração total. Essa aproximação não
usa timestamps palavra a palavra e pode errar com pausas/velocidade variável.
Repetir `finish` devolve o mesmo relatório persistido. O painel público mostra
os pontos e trechos curtos após a conclusão; o LCD mostra um cartão curto.
Transcrição completa continua fora do painel público. Cobertura não comprova
correção factual nem domínio do assunto.

## Expressão, transporte e compatibilidade

Durante captura real guiada, frames JSON Lines `type: content` são provisórios,
sem áudio nem transcrição. Contêm `v`, `request_id`, `session_id`, `state`,
`is_demo`, `origin`, `seq`, `status`, `expression` e `coverage_percent`.
O teto segue 4096 bytes; o worker emite no máximo uma atualização por janela,
com limite configurável `guided_serial_max_hz` (padrão 0,5 Hz). O firmware
descarta frames antigos, duplicados, de outra sessão ou malformados sem concluir
a sessão. Somente `type: result` validado pelo fluxo NM-001 pode mostrar sucesso.
O prefixo `c2-` no `request_id` dos dispositivos atualizados anuncia suporte ao
frame novo sem alterar a estrutura dos comandos. Firmware antigo envia IDs sem
esse prefixo e não recebe frames de conteúdo. Mac antigo aceita o novo ID como
texto comum e mantém os estados antigos.

O avatar mantém a silhueta original com laço e os temas existentes. Duas
atualizações iguais e pelo menos 6 s entre trocas suavizam a expressão. Uma
inversão explícita pode produzir expressão triste; após 30 s de fala reconhecida
sem cobertura, preocupada; conteúdo parcial, contente; cobertura, feliz.
Microfone baixo/clipping bloqueia atualização de expressão. Sem conteúdo ou sem
batimento, a expressão antiga continua. O texto curto acompanha o rosto para
não depender só de cor/expressão. Nenhuma reação antecipa conclusão.

## Configuração e medições

`NEKOMIND_GUIDED_LIVE_ENABLED=false` desliga apenas o feedback provisório;
o relatório final guiado continua. `NEKOMIND_GUIDED_PARTIAL_INTERVAL_SECONDS`
aceita 3–30 s (padrão 6), `NEKOMIND_GUIDED_WINDOW_SECONDS` aceita 6–30 s
(padrão 12), `NEKOMIND_GUIDED_SERIAL_MAX_HZ` aceita 0,1–2 (padrão 0,5).
Use apenas modo real com modelo ASR local previamente instalado para parciais.
No modo demo, o relatório é explicitamente simulado e não há reações ao vivo.

Medição local em 28/09/2026: Mac Apple M4 Max, macOS 26.6.2, modelo local
`faster-whisper-small`, CPU/int8, fala **sintetizada localmente** pela voz
Luciana (17,97 s), backend TestClient e SQLite temporário. Primeiro parcial
incluindo carga do modelo: 2,44 s; transcrição final após aquecimento: 2,12 s;
RSS máximo após o primeiro parcial: 1.069.711.360 bytes (base 73.826.304).
Batimento de dois pontos: 0,138 ms de CPU por relatório, média de 1000 chamadas
sintéticas. Em alimentação quase em tempo real: 3 parciais com latências de
1,61/1,51/1,64 s, ~0,135 frame/s, 0 janelas descartadas; transcrição final
após parar worker: 2,00 s. Esse ensaio **não** mede microfone humano, serial
físico, LCD, ruído da sala, carga concorrente de outros apps ou tempo da sessão
completa no evento; repetir a medição nessas condições antes da apresentação.
Com o mesmo WAV sintetizado, a transcrição final antes e depois de um parcial
foi textualmente idêntica (48 palavras finais; o parcial tinha 31). Isso
verifica o caminho ASR nesse arquivo, não a qualidade geral do reconhecimento.

## Testar

```bash
cd backend
NEKOMIND_MODE=demo .venv/bin/python -m pytest -q
cd ..
node --test frontend/tests/*.test.mjs
bash iot/nekomind_firmware/scripts/test_firmware.sh
```

Para o ensaio físico, seguir [validação manual](manual-validation.md) e
[roteiro da apresentação](day-of-rehearsal.md). Testes automatizados usam
microfone/ASR/serial substitutos ou áudio sintetizado; não comprovam a reação
visual nem a latência da placa real.

## Mapa de entrega e pendências

| Item | Código principal | Evidência automatizada | Ainda validar |
| --- | --- | --- | --- |
| NM-020 | `database/models.py`, `database/connection.py`, `api/routes_content.py`, `api/routes_sessions.py`, painel operador | CRUD, snapshot, reenvio e migração SQLite legado | Importar conteúdos reais autorizados e conferir revisão dos pontos |
| NM-021 | `mac/capture.py`, `mac/partials.py`, `adapters/asr_adapter.py`, `mac/bridge.py` | Fila limitada, parada e transcrição final idêntica no WAV TTS | Voz humana, CPU/memória/latência com outros apps e finalização concorrente |
| NM-022 | `services/content_matching.py`, `mac/bridge.py` | aderente/parcial/alheio/vazio/ruído/inversão explícita; medição CPU sintética | Calibrar vocabulário e limiares com falas reais |
| NM-023 | `neko_controller.c`, `neko_layout.c`, `display_ui.c` | estados e texto no host C, tema/redução de movimento | Legibilidade, suavização e toque no LCD físico |
| NM-024 | `services/session_analysis.py`, `schemas/session.py`, `routes_experience.py`, painel público | relatório persistido, idempotência e origem | Legibilidade do relatório no Mac/display da feira |
| NM-025 | `mac/protocol.py`, `neko_protocol.c`, `neko_controller.c` | frame limitado, sessão/ordem/duplicata, compatibilidade lógica | Teste USB entre firmware novo e Mac na bancada |
