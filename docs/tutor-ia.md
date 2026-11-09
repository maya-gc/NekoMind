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
  do bridge; se demorar mais de 25 s ou falhar, as regras locais assumem.
- **Modelo:** `NEKOMIND_TUTOR_MODEL=qwen2.5:7b` (melhor em temas avançados; GPU
  ajuda). Em máquina fraca: `qwen2.5:3b`.

## Estudar um tema complexo

1. Em `/presenter`, cole um texto sobre o tema (artigo, apostila, PDF ou URL) e
   revise os pontos — de preferência **um conceito por ponto** (“A Hamiltoniana
   é o operador da energia total”).
2. No display, escolha a missão, explique, finalize. A gatinha pergunta sobre o
   que faltou; peça dica; responda de novo; veja a comparação.

## Limites

A IA pode errar em física avançada: trate pergunta e comparação como estímulo
de estudo, não como correção oficial. A cobertura exibida no `/public` continua
lexical. Teste automático: `python -m app.devtools.pipeline --cenario complexo --tutor ia`.

## Preparar e testar no Windows (você mesma)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\preparar_windows.ps1   # uma vez
powershell -ExecutionPolicy Bypass -File scripts\testar_eu_mesma.ps1    # cada teste
```
