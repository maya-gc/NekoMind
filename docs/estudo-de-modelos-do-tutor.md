# Avaliação da fala nas missões do NekoMind

## Caso observado na bancada

Na missão “Quanto é 4 mais 1?”, o histórico registrou a soma e a explicação com cadeiras. O percentual exibido media menções aos pontos do material inteiro. A segunda resposta também deixou de receber crédito porque a análise anterior falhou ao interpretar a formulação oral da soma.

O teste de regressão cobre a explicação com cadeiras, uma fala equivalente em ordem inversa com bolinhas e a apresentação do parecer sem percentual de palavras na tela do aluno. Uma reprodução em banco temporário percorreu o fluxo com áudio sintetizado em português, Whisper small e tutor local. O retorno foi “Você mostrou a soma com cadeiras”.

## Fluxo proposto

| Etapa | Entrada e decisão |
| --- | --- |
| Transcrição | O Whisper local registra a fala em português. A transcrição pertence à tentativa e continua disponível para revisão autorizada. |
| Análise semântica | O tutor recebe a pergunta da missão, o contexto salvo e a fala. Na segunda tentativa, recebe também a fala anterior. Identifica o raciocínio e a analogia apresentada. |
| Evidência | A avaliação cita um trecho da própria fala. Quando o modelo devolve uma citação imprecisa em uma avaliação conceitual, uma verificação curta tenta recuperar o trecho original. |
| Verificação da soma | Nas contas comportadas pelo verificador, o cálculo confere a conclusão e as relações demonstradas. Números por extenso, ordem dos grupos e objetos diferentes são aceitos. Um julgamento do modelo exige evidência para dar crédito ou apontar erro. |
| Resposta | A gatinha reconhece o que a pessoa explicou, oferece uma dica relacionada ou pede esclarecimento. O texto do LCD é validado separadamente. |
| Acompanhamento do material | A métrica de menções fica disponível no acompanhamento do operador e no histórico. O aluno vê o parecer da missão. |

O resultado de uma conta objetiva pode ser único. A avaliação aceita caminhos equivalentes e distingue uma resposta numérica de uma explicação. Fora da aritmética verificável, a evidência e o contexto da missão sustentam o parecer. O retorno admite uma categoria parcial ou uma pergunta de esclarecimento quando a fala não sustenta uma conclusão.

## Modelos e critérios de escolha

| Modelo | Artefato local | Papel no estudo |
| --- | --- | --- |
| Qwen2.5 3B | 1,9 GB | Referência instalada. Suporta português. Testado com o fluxo em dois turnos e com os casos abaixo. Sua licença é a Qwen. [Ficha no Ollama](https://ollama.com/library/qwen2.5) |
| Qwen3 4B | 2,5 GB, Q4_K_M | Candidato para substituir somente o avaliador da fala. Foi testado com o modo de pensamento desativado, suporta português e usa Apache 2.0. [Ficha no Ollama](https://ollama.com/library/qwen3:4b) · [Notas da equipe Qwen](https://qwenlm.github.io/blog/qwen3/) |
| Gemma 3 4B | 3,4 GB, Q4_K_M | Alternativa de outra família com suporte multilíngue. Candidata para uma rodada posterior com o mesmo conjunto; usa os termos do Gemma. [Ficha no Ollama](https://ollama.com/library/gemma3:4b) |

O modelo de transcrição e o modelo de avaliação têm funções distintas. A escolha do avaliador deve considerar a qualidade do parecer em português, o número de respostas corretas reprovadas, a qualidade dos trechos citados, a latência de ponta a ponta e o tratamento de transcrições incompletas. A aceitação em sala depende de testes com o público real. [Saídas estruturadas no Ollama](https://docs.ollama.com/capabilities/structured-outputs)

## Amostra de avaliação

A comparação local usa 12 falas sintéticas em português, com chamadas de primeira e segunda rodada, temperatura zero e casos iguais por configuração. Mede-se o rótulo exato do modelo e o rótulo depois da validação no fluxo. Os tempos desta amostra são tempos de avaliação sobre texto, sem microfone, Whisper, voz ou LCD.

| Caso | Rótulo esperado |
| --- | --- |
| 4 mais 1 com cadeiras | Correto |
| 1 mais 4 com bolinhas | Correto |
| Quatro livros e mais um livro empilhado | Correto |
| Um lápis e dois pares de lápis | Correto |
| Contar quatro e avançar uma posição | Correto |
| Apenas “cinco” | Parcial |
| 4 mais 1 resulta em seis | Equívoco |
| Autocorrigir seis para cinco com a analogia de mesas | Correto |
| Falar da cor e do lugar da cadeira | Fora do assunto |
| Interromper a fala depois de “comecei com quatro” | Parcial |
| Comparar roupa secando a uma poça que vai para o ar | Correto |
| Explicar que a roupa seca porque a água vira gelo | Equívoco |

A amostra é exploratória. A validação em crianças exige gravações autorizadas e variadas, incluindo fala espontânea, sotaque, pausas, autocorreção e ruído de sala. O erro prioritário a medir é a gatinha tratar uma explicação válida como equívoco.


## Resultados da rodada

| Versão avaliada | Parecer do modelo | Parecer do fluxo | Mediana por fala | Máximo por fala |
| --- | ---: | ---: | ---: | ---: |
| Qwen2.5 3B com o primeiro formato testado | 5/12 | 10/12 | 2,53 s | 4,28 s |
| Qwen2.5 3B com extração de evidência e verificação aritmética | 8/12 | 11/12 | 3,03 s | 6,04 s |
| Qwen3 4B com a mesma estrutura | 7/12 | 11/12 | 2,31 s | 2,95 s |

Com a estrutura final, nenhum dos modelos classificou uma explicação correta como equívoco. O Qwen2.5 marcou a fala sobre a cor da cadeira como parcial. O Qwen3 acertou esse caso e marcou a analogia correta de evaporação como parcial. A validação corrigiu classificações indevidas em casos como o total errado, a fala interrompida e a resposta que trazia apenas o número. A latência foi observada no Mac da bancada em uma rodada curta, com carga de fundo variável.

A bancada mantém o Qwen2.5 3B para avaliação ampla. O Qwen3 4B fica instalado como candidato para um piloto com mais analogias de matemática e ciências. O empate no conjunto pequeno e a diferença no caso conceitual pedem uma amostra maior antes de trocar o padrão. O benefício observado com mais consistência veio da avaliação sobre a transcrição, da validação da evidência e da checagem da conta.

A bancada passou por regressão de backend, testes do painel web e uma reprodução da missão com áudio, Whisper small e verificação das duas chamadas ao tutor. Os dois modelos passaram pela reprodução da missão das cadeiras com o Whisper small. O ESP confirmou por USB a tela pronta na missão 3.

Para a validação de vozes reais, convém anotar separadamente os números e as operações que a criança disse, a relação matemática ou conceitual que explicou, e o parecer apresentado. Isso permite medir trocas de números no ASR, falhas de avaliação sobre uma fala bem transcrita e atrasos de resposta. O conjunto deve incluir mais de uma maneira correta de responder à mesma missão e frases que usam o mesmo objeto sem explicar a ideia pedida.
