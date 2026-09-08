# NekoMind Frontend (Streamlit)

Dashboard lúdico do NekoMind. Regra: **nunca** acessa o banco — consome
somente a API do backend por `services/backend_client.py`.

## Rodando

```bash
# Na raiz do repositorio:
bash scripts/setup_frontend.sh   # ou scripts\setup_frontend.ps1 no Windows
bash scripts/run_frontend.sh     # ou scripts\run_frontend.ps1
```

Abre em `http://127.0.0.1:8501`.

## Páginas

- **1. Dashboard** — sessões, tempo estudado, clareza média, tópicos e evolução;
- **2. Sessões** — lista/detalhe, transcrição, métricas e avatar por estado;
- **3. Tópicos** — conceitos mais frequentes e árvore por sessão;
- **4. Configurações** — URL do backend e modo de demonstração.

## Modo demonstração

Sem backend com IA, o dashboard funciona com sessões fictícias `[DEMO]`
geradas pelos adapters mock. O botão "Nova sessão (demo)" na página
**Sessões** cria e analisa uma sessão diretamente na API.