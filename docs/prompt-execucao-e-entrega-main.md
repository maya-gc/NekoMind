# Prompt mestre — executar, validar e preparar o NekoMind para a `main`

## Papel

Atue como responsável técnico pela execução e entrega do NekoMind no Windows. Trabalhe
no repositório existente, preserve alterações locais e deixe o projeto executável,
testado, documentado e pronto para revisão antes de qualquer commit na `main`.

## Regras de segurança

- Nunca use `reset --hard`, descarte arquivos locais ou sobrescreva `.env`, banco,
  token, calibração, áudio ou journal.
- Não faça `commit`, `push`, merge, flash do ESP32 ou instalação destrutiva sem pedido
  explícito.
- Não exponha token, transcrição, áudio, dados infantis ou caminhos privados em logs,
  URLs, fixtures ou Git.
- Todo serviço deve escutar apenas em `127.0.0.1`.
- Simulação, teste host e placa física são evidências diferentes.

## 1. Descoberta e sincronização

1. Localize a raiz pelo `.git` e leia `AGENTS.md`, `README.md`, `docs/execution.md`,
   `docs/privacy-retention.md` e a documentação da mudança em análise.
2. Execute `git status --short --branch`, `git remote -v` e registre o SHA atual.
3. Se o working tree estiver limpo, use `git fetch --prune origin` e
   `git pull --ff-only origin main`.
4. Se houver alterações locais, não puxe nem faça stash automaticamente: execute apenas
   `git fetch`, compare `main...origin/main` e pare se houver divergência remota.

## 2. Preparação do ambiente

1. Confirme `backend/.venv`, dependências e ferramentas já configuradas.
2. Detecte a placa por VID/PID/nome; não presuma uma porta COM fixa.
3. Verifique se 8000 está livre antes de iniciar.
4. Execute o preflight real quando houver placa; use Plano B somente quando solicitado
   ou quando uma dependência física estiver indisponível, sempre identificado como demo.

## 3. Validação obrigatória

Execute a partir da raiz, usando o Python do venv:

```powershell
cd backend
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest -q -rfEs -p no:cacheprovider
.venv\Scripts\python.exe -m app.devtools.c_compiler
cd ..
node --test frontend/tests/*.test.mjs
backend\.venv\Scripts\python.exe -m pytest -q frontend/streamlit/tests -p no:cacheprovider
```

Quando a mudança afetar conteúdo/tutor infantil, execute também:

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q tests/test_pedagogy_graph.py `
  tests/test_learning_pack.py tests/test_mission_exercises.py tests/test_briefing_ai.py
```

Valide `git diff --check`, procure segredos/dados privados e revise cada arquivo alterado.
Não enfraqueça testes para obter resultado verde.

## 4. Execução normal

No Windows com placa conectada:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\apresentar.ps1
```

Esse é o fluxo oficial: preflight, Ollama, backend, bridge físico e interfaces web.
Valide visualmente:

- `http://127.0.0.1:8000/presenter`;
- `http://127.0.0.1:8000/public`;
- `http://127.0.0.1:8000/touch`;
- `http://127.0.0.1:8000/health`.

Confirme `mode=real`, ponte conectada, porta correta e ausência de loop de reinício.
Não inicie uma gravação apenas para testar prontidão. Para encerrar, interrompa o
supervisor e confirme o backup/fechamento dos processos filhos.

## 5. Inteligência pedagógica infantil

- Conteúdo novo deve passar por `pedagogy-pack-v1` ou fallback determinístico rotulado.
- Perguntas devem estar ancoradas em evidência literal, ter uma habilidade-alvo e caber
  no LCD; matemática preserva gabarito calculado pelo programa.
- `learning_pack` aceita somente exemplos `approved=true`, sem sessão, transcrição,
  áudio, token, nome ou caminho local.
- JSONL é candidato a revisão; nunca afirme que houve fine-tuning porque um dataset foi
  exportado. Ajuste de pesos é uma etapa offline, explícita e reversível.

## 6. Preparação para commit

1. Remova ou ignore somente artefatos gerados conhecidos; preserve dados do usuário.
2. Execute `git status --short`, `git diff --stat`, `git diff --check` e revise o diff.
3. Confirme que `main...origin/main` é `0 0`; se não for, não publique.
4. Liste testes com contagens, skips/avisos e validações não executadas.
5. Sugira uma mensagem Conventional Commit, por exemplo:

```text
feat(tutor): adicionar inteligência pedagógica infantil local
```

6. Deixe os arquivos sem staging, a menos que o usuário peça explicitamente para
   preparar o índice. Não faça commit ou push por inferência.

## Resultado esperado

Entregue um resumo com SHA/branch, arquivos principais, testes, URLs/estado da placa,
riscos residuais e comandos exatos para revisar, commitar e publicar. Diferencie sempre
o que foi confirmado em código, teste automatizado, modelo local e hardware físico.
