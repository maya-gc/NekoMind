# Inteligência pedagógica local para público infantil

Esta primeira versão adiciona planejamento pedagógico verificável sem alterar pesos do
modelo e sem aprender automaticamente com falas de crianças.

## O que está implementado

- `app.services.pedagogy_graph` cria o contrato `pedagogy-pack-v1`.
- Conceitos sempre apontam para evidência literal do material.
- Habilidades e relações usam enum fechado; índices, duplicatas, arestas e ciclos de
  pré-requisito são validados.
- O Ollama pode organizar os pontos, mas não escreve a evidência. Se estiver ausente ou
  responder fora do schema, a origem muda explicitamente para `deterministic`.
- A geração atual de missões monta localmente um subgrafo determinístico e o inclui,
  como dado não executável, na chamada que já existia. Isso não adiciona outra chamada
  obrigatória nem remove o gerador determinístico de somas.
- `app.devtools.learning_pack` valida, importa e exporta exemplos curados.

O grafo é um plano de conceitos e habilidades. Não é nota, diagnóstico, domínio do
conteúdo nem prova de correção factual.

## Construir um grafo com Ollama

```python
from app.services.pedagogy_graph import build_pedagogy_pack

pack = build_pedagogy_pack(
    "Ciclo da água",
    "A água evapora com o calor. Depois o vapor esfria e forma gotas.",
    [
        "A água evapora com o calor.",
        "Depois o vapor esfria e forma gotas.",
    ],
    "qwen2.5:7b",
)
```

`provenance.provider` informa `ollama_local` ou `deterministic`. O consumidor deve
sempre validar o pack antes de usá-lo e preservar `source_hash` e `method_version`.

## Pacote portátil curado

O formato `nekomind-learning-pack-v1` aceita somente exemplos com `approved: true`,
`source_hash`, `instruction` e `response`. Campos ou valores que pareçam transcrição,
áudio, token, id de sessão, nome, caminho local, e-mail ou telefone são recusados.

Validar:

```powershell
cd backend
.venv\Scripts\python.exe -m app.devtools.learning_pack validate .\pack.json
```

Importar de forma idempotente para um arquivo local:

```powershell
.venv\Scripts\python.exe -m app.devtools.learning_pack import .\pack.json `
  --store .\storage\learning-pack.json
```

Gerar corpus revisável:

```powershell
.venv\Scripts\python.exe -m app.devtools.learning_pack export-jsonl `
  .\storage\learning-pack.json --out .\storage\fine-tuning-candidate
```

A saída contém `train.jsonl`, `validation.jsonl` e `manifest.json`. A separação é
determinística por `source_hash`, sem duplicar o mesmo exemplo entre conjuntos. O
manifesto registra modelo-base, licença declarada, hashes, versão do prompt e
`trained: false`.

## Limites e próximos passos

- Nenhum fine-tuning foi executado. O JSONL é apenas candidato para revisão.
- Não houve validação pedagógica com crianças ou especialistas nesta implementação.
- O grafo com Ollama ainda não é persistido na biblioteca de conteúdos; o subgrafo
  usado no fluxo atual é recalculado deterministicamente em memória.
- Antes de treinar, é necessário confirmar licença do modelo/base e dos exemplos,
  revisar cada par, fixar um conjunto de avaliação infantil e comparar com o baseline.
- Um modelo ajustado nunca deve substituir automaticamente o modelo em produção.
- Sessões privadas, áudio e transcrições continuam sujeitos à retenção/exclusão e não
  podem ser derivados para o corpus sem aprovação humana específica.
