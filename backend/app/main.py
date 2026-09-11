"""Aplicacao FastAPI do NekoMind."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.adapters.asr_adapter import clear_asr_cache
from app.api import routes_audio, routes_experience, routes_health, routes_sessions, websocket
from app.config import get_settings
from app.database.connection import init_db
from app.security import operator_token, require_operator


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Garante que o diretorio de armazenamento exista antes do banco/audio.
    get_settings().storage_dir.mkdir(parents=True, exist_ok=True)
    operator_token()
    init_db()
    try:
        yield
    finally:
        clear_asr_cache()


app = FastAPI(
    title="NekoMind Backend",
    version="0.1.0",
    description=(
        "Backend do NekoMind: ingestao de audio, transcricao (ASR), "
        "extracao de topicos (LLM) e metricas heuristicas de clareza. "
        "Modo mock por padrao - sem chaves de API e sem download de modelos."
    ),
    lifespan=lifespan,
)

# CORS aberto apenas para desenvolvimento local (frontend Streamlit).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8501", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_sessions.router, dependencies=[Depends(require_operator)])
app.include_router(routes_audio.router, dependencies=[Depends(require_operator)])
app.include_router(routes_experience.router)
app.include_router(websocket.router)

WEB_DIR = Path(__file__).resolve().parents[2] / "frontend" / "web"
app.mount("/web", StaticFiles(directory=WEB_DIR, check_dir=False), name="web")


@app.get("/touch", include_in_schema=False)
@app.get("/public", include_in_schema=False)
@app.get("/presenter", include_in_schema=False)
def panel():
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store"})
