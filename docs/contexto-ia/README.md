# Contexto de IA do NekoMind — índice consolidado

Consolidado em 08/11/2026 a partir das 4 branches do repositório `maya-gc/NekoMind`;
atualizado em 09/11/2026.

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

## Linha do tempo das sessões de IA

| Data | Ferramenta | O que foi decidido/feito | Onde está |
|---|---|---|---|
| 19–21/09/2026 | Agentes (architect → coder → tester → reviewer) | Plataforma LCD Touch, protocolo JSON Lines, referência técnica de hardware | `pipeline/` |
| até 29/10/2026 | Codex/ChatGPT | Arquitetura ESP + Mac, voz Kokoro, diálogo de duas respostas, testes de bancada | [`../handoff-colaborador.md`](../handoff-colaborador.md) |
| 08/11/2026 | Claude | Branches unidas em `main` com todo o histórico; este índice | este arquivo |
| 09/11/2026 | Claude | Suporte a Windows sem mudar o caminho do Mac; pipeline automática silenciosa (toque virtual, voz do sistema, gatinha sem som) e pipeline de bancada; teste de fumaça da placa na bancada Windows (COM3) | [`../pipelines-de-teste.md`](../pipelines-de-teste.md), [`sessao-2026-11-09-windows.md`](sessao-2026-11-09-windows.md) |
