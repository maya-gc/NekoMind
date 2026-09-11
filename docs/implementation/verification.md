# Evidência de verificação

Registro histórico da verificação de 10/09/2026. Ele não é a evidência final da rodada
NM-001..019. Ambiente local macOS, Python3.12 no venv backend, somente fixtures
sintéticas/demonstração. Microfone e modelos são substitutos; PTY usa dispositivo
virtual POSIX real, sem ESP. Resultados atuais ficam no relatório de QA da entrega.

## Regressões observadas antes da correção

- ASR instanciava por chamada;7 falhas nos primeiros9 testes; cache/lifecycle passaram
  com10 testes após integração lifespan. O log RED salvo preservou timestamp usado
  para corrigir registro estruturado preenchido incorretamente com timestamp GREEN.
- Modo/provedor, tópicos infundados, silêncio real, duplicação de início/finalização,
  uploads concorrentes e capture-state stale tiveram testes falhando antes dos patches.
- Bridge confirmava pause sem status correspondente; aceitava bool no id do tópico;
  encerramento do writer permitia nova captura cedo; processing retornado pelo backend
  virava erro definitivo. Quatro regressões falharam juntas e depois passaram.
- Versão JSON true/1.0 era aceita como1: dois testes RED e depois GREEN com validação de tipo.
- Falha de backup SQLite permitia prosseguir com cópia insegura em WAL: RED e depois
  GREEN com bloqueio de migração antes de alterar colunas.
- Commit de chunk falho deixava arquivo órfão; refresh pós-commit falho derrubava retorno:
  RED/GREEN com raw imutável único e banco como manifesto de publicação.
- Firmware: erro tardio derrubava sucesso, statusidle null era inválido e pause aceitava
  recording. Probes/revisões independentes confirmaram correções finais; teste host passou.

Isso registra evidência efetivamente observada; não atribui TDD a todos os arquivos
ou à criação inicial de APIs que só produziu falha de compilação.

## Browser — Data / Tree / Display / Doing

Navegador Codex local em `127.0.0.1:8501`, backend temporário loopback com SQLite fora
do repositório. Botão demo criou uma sessão de2s de silêncio e dados mock; na tela
apareceram completed, aviso demo, ASRmock/tópicosmock e métricas heurísticas.
A consulta posterior conservou resultado; Tab moveu do botão à seleção de sessão.
No viewport estreito, menu foi recolhido e controles/rótulos ficaram visíveis.
Configuração real de teste não executou ASR: somente demonstrou bloqueio do botão demo
com histórico ainda identificado. Ao parar backend, Configurações apresentou erro.

- [Demo desktop](../../ScreenshotsToCloseLoop/runs/touch-mac-mvp/streamlit-demo.png)
- [Demo390×844](../../ScreenshotsToCloseLoop/runs/touch-mac-mvp/streamlit-demo-mobile.png)
- [Demo bloqueada no modo real](../../ScreenshotsToCloseLoop/runs/touch-mac-mvp/streamlit-real-demo-blocked.png)
- [Backend indisponível](../../ScreenshotsToCloseLoop/runs/touch-mac-mvp/streamlit-backend-error.png)

Os servidores temporários foram encerrados após verificação. Screenshots não contêm
conteúdo pessoal. Sem auditoria completa WCAG nem evidência de touch físico. Gate UI
estruturado do Flow permaneceu FAIL; screenshots não substituem suas demais exigências.
