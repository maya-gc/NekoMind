# Tutor IA local — temas simples e complexos

Desde 09/11/2026 a pergunta, a dica e a comparação podem ser geradas por um
modelo local no **Ollama** (padrão `qwen2.5:7b`), lendo o ponto da missão e o
que você falou. Assim funcionam tanto “ciclo da água” quanto “Hamiltoniana” ou
“computação quântica”: a pergunta mira o que faltou ou o que ficou impreciso na
sua explicação, a dica orienta sem entregar a resposta e a comparação diz o que
melhorou e o que ainda falta.

- **Automático e offline:** `NEKOMIND_TUTOR_PROVIDER=auto` (padrão) usa a IA se o
  modelo estiver instalado; senão, as regras locais de antes assumem. Nada vai
  para a nuvem.
- **Limites da tela:** pergunta ≤ 140 bytes, dica ≤ 120, comparação ≤ 94.
- **O touch não trava:** a IA roda antes de publicar o resultado, fora da trava
  do bridge; se demorar mais de 40 s ou falhar, as regras locais assumem.
- **Modelo:** `NEKOMIND_TUTOR_MODEL=qwen2.5:7b` (melhor em temas avançados; GPU
  ajuda). Em máquina fraca: `qwen2.5:3b`.

## Estudar um tema complexo

1. Em `/presenter`, cole um texto sobre o tema (artigo, apostila, PDF ou URL) e
   revise os pontos — de preferência **um conceito por ponto** (“A Hamiltoniana
   é o operador da energia total”).
2. No display, escolha a missão, explique, finalize. A gatinha pergunta sobre o
   que faltou; peça dica; responda de novo; veja a comparação.

## Novidades de 10/11/2026

- **Avaliação por significado:** a IA classifica cada fala como correta,
  parcial, com equívoco ou não mencionada — paráfrases valem. Se houver
  equívoco, a pergunta leva você a perceber o erro.
- **Dicas graduais:** cada toque em **Pedir dica** traz uma dica mais forte
  (pista → analogia → começo de exemplo).
- **Vocabulário técnico:** os termos do material orientam a transcrição
  (“Schrödinger”, “autovalores”).
- **Níveis:** `NEKOMIND_TUTOR_LEVEL=crianca|enem|faculdade` muda o tom.
- **Memória:** o resultado de cada ponto fica no diário local e entra no
  contexto da próxima pergunta sobre o mesmo ponto; `review_queue()` lista o
  que revisar.
- **Decks prontos:** `python -m app.devtools.decks` importa 3 temas simples e
  2 complexos para a biblioteca do `/presenter`.

Ainda não feito: mais de duas rodadas por missão e escolha de deck/nível pelo
display (exigem mudar firmware e protocolo); fila de revisão ainda não aparece
nas telas; avaliação da IA não substitui a cobertura lexical do `/public`.

## Medir a qualidade da IA

`python -m app.devtools.tutor_eval` (na pasta `backend`, com o Ollama ligado)
julga 24 falas de referência — temas simples e avançados, certas, parciais, com
equívoco e fora do ponto — e mostra acerto exato, acerto tolerante, tabela de
confusão e tempo médio. Use `--modelo qwen2.5:14b` para comparar modelos.

**Resultado com `qwen2.5:7b` (10/11/2026, Windows, GPU NVIDIA):**

| Versão | Exato | Tolerante | Observação |
|---|---|---|---|
| Pedido inicial | 10/24 | 16/24 | Chamava respostas incompletas de “equívoco” |
| Rubrica com exemplos + conferência dupla | **13/24** | **22/24** | Equívocos 5/6; incompleto não vira mais erro |
| Mesma rubrica, sem conferência dupla | 11/24 | 18/24 | Aceita fala de outro ponto como “correta” |

O ponto fraco que resta é separar “parcial” de “não falou deste ponto” (5
casos). Uma regra por palavras resolveria alguns, mas passaria a dizer “você
não falou disso” para quem respondeu em parte — por isso não foi adotada.
Próximo passo natural: comparar com um modelo maior (`--modelo qwen2.5:14b`).

**Conferência dupla:** se a IA disser “correto” mas a fala não tiver nenhum
termo do ponto da missão, o resultado vira “parcial” (equívocos nunca são
suavizados).

**Nas telas:** o `/public` mostra a avaliação da IA (“Explicou o ponto”, “Explicou
em parte”, “Há um equívoco para rever”, “Ainda não falou deste ponto”), sempre
com o aviso de que não é nota. O `/presenter` mostra **Revisar hoje** com os
pontos que ainda não ficaram corretos.

## Limites

A IA pode errar em física avançada: trate pergunta e comparação como estímulo
de estudo, não como correção oficial. A cobertura exibida no `/public` continua
lexical. Teste automático: `python -m app.devtools.pipeline --cenario complexo --tutor ia`.

## Preparar e testar no Windows (você mesma)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\preparar_windows.ps1   # uma vez
powershell -ExecutionPolicy Bypass -File scripts\testar_eu_mesma.ps1    # cada teste
```
