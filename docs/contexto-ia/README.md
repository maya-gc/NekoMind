# Contexto de IA do NekoMind — índice consolidado

Consolidado em 08/11/2026 a partir das 4 branches do repositório `maya-gc/NekoMind`.

## Onde está cada parte do contexto

| Material | Origem | O que é |
|---|---|---|
| [`docs/handoff-colaborador.md`](../handoff-colaborador.md) | branch `codex/nekomind-current-snapshot` | **Ponto de entrada.** Síntese das decisões da sessão com o Codex/ChatGPT (arquitetura, voz, testes, pendências) + link da conversa compartilhada. |
| [`docs/interactive-dialogue.md`](../interactive-dialogue.md), [`docs/setup-log.md`](../setup-log.md) | snapshot | Contrato do diálogo no touch e log de setup. |
| [`pipeline/prompt_plataforma_nekomind_lcd_touch.md`](pipeline/prompt_plataforma_nekomind_lcd_touch.md) | branch `pipeline` | Prompt mestre usado para gerar a plataforma LCD Touch. |
| [`pipeline/PLAN.md`](pipeline/PLAN.md) | `pipeline` | Grafo de tarefas para os agentes (architect → coder → tester → reviewer). |
| [`pipeline/LOOP_LOG.md`](pipeline/LOOP_LOG.md) | `pipeline` | Registro das iterações dos agentes (Iteração 0 e 0.1). |
| [`pipeline/TECHNICAL_REFERENCE.md`](pipeline/TECHNICAL_REFERENCE.md) | `pipeline` | "Memória técnica permanente" para sessões de IA: hardware, pinagem, decisões críticas. Tem problemas de codificação (UTF-8 lido como Latin-1) no original. |
| [`pipeline/requirements.txt`](pipeline/requirements.txt) | `pipeline` | Dependências da plataforma Touch Lab. |
| `output/pdf/`, `experiments/` | snapshot | Estudos gerados durante a exploração (hipótese B, análise A3, voz). |
| Conversa completa | fora do Git | https://chatgpt.com/s/cx_6ae3caae8cf88191b66318c2b8de9ba4 (link de leitura) |
| Página no Notion | fora do Git | citada no handoff; histórica, não 100% atualizada. |

**Observação:** nenhuma branch contém transcrições brutas de sessões (.jsonl, histórico de chat).
O registro integral da conversa está apenas no link do ChatGPT acima.
