# Auditoria e melhoria do NekoMind — 20/11/2026

## Sincronização

- Repositório: `maya-gc/NekoMind`.
- Branch: `main`.
- Estado inicial: limpo, um commit atrás de `origin/main`.
- Atualização: fast-forward de `7a15aad` para `6df9991` por `git pull --ff-only`.
- Estado após atualização: `main` alinhada com `origin/main`; as mudanças desta
  auditoria permanecem locais e não foram enviadas ao remoto.

## Achados corrigidos

### P1 — falso acerto em somas

Uma simples menção ou negação do resultado esperado podia preservar um parecer
`correto` produzido pelo tutor, mesmo sem confirmação do verificador determinístico.
Agora, em exercícios estruturados de soma, o parecer só permanece `correto` quando a
explicação também é confirmada pelo verificador. Há regressões para “não é 5, é 4”,
“5 está errado” e “acho 5, mas não”.

### P1 — fallback incompatível com o LCD

Quando o Ollama não devolvia exercícios válidos, `prepare_questions()` podia repassar
pontos longos, metadados ou frases sem pergunta. O fallback agora valida o limite do
LCD, converte pontos aproveitáveis, preserva até 30 missões e usa uma pergunta fixa
segura quando necessário. Perguntas já preparadas são reutilizadas, evitando textos
duplicados como “O que sabe sobre O que sabe sobre...”.

### P2 — instruções importadas no prompt do tutor

Material de PDF/site e transcrições eram interpolados sem uma fronteira inequívoca de
dados não confiáveis. A política do sistema agora declara essas entradas como dados não
executáveis; os prompts usam blocos JSON delimitados e limites explícitos. Um teste
adversarial inspeciona o payload enviado ao modelo.

### P2 — parser e classificação de missões

- O parser de Markdown agora aceita texto introdutório entre o título “Missões” e os
  itens, encerrando em um novo heading.
- A detecção de matemática básica não descarta material longo e reconhece soma, adição
  e contagem para iniciantes/até 10, mantendo exclusões conservadoras para cálculo,
  álgebra linear, trigonometria e conteúdo avançado.

### P2 — qualidade e CI

Os oito achados Ruff do baseline foram corrigidos, inclusive estado mutável em classes
de teste. A CI passou a executar `python -m ruff check .` no backend. Dois imports de
experimentos de voz também foram normalizados para que o Ruff do repositório completo
fique verde.

### P2 — inteligência pedagógica infantil

Foi adicionado o contrato `pedagogy-pack-v1`, com conceitos ancorados em evidência
literal, habilidades, relações, validação de índices/arestas e rejeição de ciclos de
pré-requisito. O subgrafo infantil orienta a geração de perguntas sem acrescentar uma
chamada obrigatória ao modelo e sem remover o gabarito determinístico de somas.

O utilitário `app.devtools.learning_pack` prepara somente exemplos aprovados para
portabilidade e eventual ajuste offline: valida checksum, bloqueia campos privados,
deduplica e separa treino/validação por hash do conteúdo. Ele não aprende com sessões,
não transporta transcrição/áudio e não executa fine-tuning.

### P3 — prompt e documentação obsoletos

O prompt mestre não aponta mais para `Desktop\\esp32_lcd_test`, não cria um segundo
projeto e não trata a antiga feature branch como destino ativo. Ele agora exige
sincronização segura, auditoria baseada em evidências, testes, privacidade e separação
entre software, simulação e hardware. README, diálogo interativo e protocolo foram
atualizados para a `main`, para o limite atual de 44 bytes e para o tutor local.

## Validação executada

| Verificação | Resultado |
|---|---|
| Ruff, repositório completo | aprovado |
| Backend pytest | 269 aprovados, 4 ignorados, 10 avisos |
| Frontend web Node | 44/44 aprovados |
| Frontend Streamlit | 6/6 aprovados |
| Firmware em compilador C do host | 2 suítes aprovadas |
| Pipeline virtual completo | aprovado após a correção do texto duplicado |
| Preflight plano B, sem placa e voz silenciosa | pronto para apresentar |
| Grafo local com Ollama `qwen2.5:7b` | 3 conceitos ancorados e 2 relações válidas |
| Preflight real anterior ao reinício | COM3, microfone, ASR, voz e tutor aprovados |
| `git diff --check` | aprovado |

Os quatro skips no Windows cobrem PTY/`termios` e criação de links simbólicos sem o
privilégio necessário. Os dez avisos são `StarletteDeprecationWarning`: o `TestClient`
de teste não deve receber `timeout`; não houve falha funcional.

## Riscos e pendências

1. O firmware físico ainda mostra o título genérico “Comparacao” em `stage=done`,
   enquanto a web usa o veredito simplificado. Levar `assessment` ao protocolo serial
   exige mudança coordenada de bridge, parser C, controlador, layout e testes de
   compatibilidade; não foi feito silenciosamente nesta auditoria.
2. O preflight real e a tela física foram observados antes do reinício, mas o dispositivo
   COM3 deixou de aparecer no Windows depois que os processos foram encerrados. É
   necessário reconectar/verificar o cabo antes de subir novamente o bridge real.
3. Permanecem dez avisos de depreciação do Starlette no adaptador de testes.
4. Cobertura de testes não está configurada; as contagens acima demonstram execução,
   não percentual de linhas/branches cobertas.

## Próximos passos recomendados

1. Definir uma extensão compatível do protocolo para transportar o desfecho compacto
   ao firmware e criar teste de paridade web/ESP.
2. Remover o `timeout` por requisição quando o cliente injetado for `TestClient`, sem
   alterar o timeout do cliente HTTP real.
3. Rodar o build ESP-IDF da CI e depois o roteiro de bancada com a unidade física,
   registrando separadamente compilação, simulação e observação real.
4. Adotar cobertura incremental para os módulos de sessão, tutor e protocolo.
5. Persistir `pedagogy-pack-v1` na biblioteca de conteúdos após revisão do operador;
   nesta primeira versão o subgrafo do fluxo é recalculado em memória.
