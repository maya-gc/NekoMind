# Diálogo guiado no touch

O estudante escolhe no touch um exercício curto preparado a partir do conteúdo
selecionado no Mac e explica seu raciocínio. O ESP32-S3 controla a tela e envia
comandos; o Mac capta o áudio, transcreve, avalia a resposta com regras locais e,
quando disponível, com o tutor Ollama local, e toca a voz da gatinha. O navegador
`/touch` reproduz os mesmos comandos para ensaio. O modo livre segue disponível.

## Sequência para o estudante

1. O operador seleciona um briefing revisado, com até 30 pontos. Antes da captura,
   o bridge prepara até 30 exercícios/perguntas que caibam no LCD. Para matemática
   básica, contas estruturadas recebem avaliação determinística; nos demais temas,
   o Ollama local pode propor perguntas e há fallback seguro quando indisponível.
   O touch percorre as missões com **Anterior/Próxima** e envia `start` com o
   índice escolhido. Cada prévia validada tem até 44 bytes UTF-8.
2. O estudante explica em voz alta e toca **Finalizar**. A análise correlaciona a
   fala com a missão escolhida e produz uma avaliação conservadora. Uma heurística
   ou resposta de modelo, isoladamente, não comprova correção factual ou domínio.
3. A gatinha apresenta uma pergunta curta de aprofundamento. O estudante pode
   tocar **Pedir dica**; a dica é curta e lida em voz alta quando a voz local está
   disponível.
4. Ao tocar **Responder**, começa outra captura, associada à primeira. Ao
   terminar, a gatinha compara como o mesmo ponto apareceu nas duas falas.
   **Encerrar** ou **Nova tentativa** permite seguir para o próximo visitante.

Pergunta, dica e comparação são formuladas localmente por regras e, quando
configurado, pelo modelo Ollama local. Conteúdo importado e transcrições são dados,
não instruções para o modelo. Não há chamada de IA generativa remota nem custo por
fala. A voz
Kokoro `pf_dora` em português brasileiro roda no Mac após a instalação inicial
dos pesos; usa o alto-falante do Mac. Antes de gravar, o áudio da gatinha é
interrompido para reduzir a chance de entrar na transcrição. Se a voz opcional
falhar, a tela e a captura continuam operando. O ESP não precisa de microfone
ou alto-falante adicionais para esse fluxo.

O acompanhamento lexical mostra **menção ao material**, não correção factual
nem domínio do assunto. O percentual no relatório público considera todos os
pontos do briefing, enquanto a missão escolhida pede apenas um; por isso não
deve ser interpretado como nota. A comparação usa exclusivamente o ponto da
pergunta e deixa essa limitação explícita. Sessões demo não geram diálogo
baseado em fala real.

## Contrato e persistência

- `state=ready` pode trazer `missions`. Apenas `start` aceita `mission_index`
  (0 a 29); o bridge confirma que a seleção e o texto dos pontos não mudaram
  antes de abrir o microfone.
- O primeiro resultado pode trazer `followup.stage=question`; `hint` muda para
  `stage=hint`; `answer` cria outra sessão e envia `stage=answering`; o segundo
  resultado envia `stage=done` com a comparação. O payload público também pode
  expor `assessment`, `source_point`, `tutor` e trechos de evidência sanitizados;
  a serial mantém um subconjunto compacto e o teto de 4096 bytes por linha.
- Índices, vínculos entre sessões e etapas do diálogo ficam no journal SQLite
  do bridge. Reiniciar o bridge recupera uma pergunta ou comparação já salva,
  sem reabrir o microfone automaticamente. O backend persiste cada tentativa
  como sessão própria.

## Validação

Os testes de backend percorrem as duas transcrições com ASR substituto,
seleção de missão, pergunta, dica, comparação, reinício e próxima missão. Os
testes host C verificam comandos e cenas 240×320; os testes Node verificam o
emulador e a sanitização do conteúdo. Ainda é necessário ensaiar no hardware
real a legibilidade do touch, a saída de áudio, o microfone, o cabo USB e a
latência sob ruído da sala. O build e o flash ESP-IDF são passos separados dos
testes host.
