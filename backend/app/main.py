"""Aplicacao FastAPI do NekoMind."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_audio, routes_health, routes_sessions, websocket
from app.config import get_settings
from app.database.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Garante que o diretorio de armazenamento exista antes do banco/audio.
    get_settings().storage_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


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
app.include_router(routes_sessions.router)
app.include_router(routes_audio.router)
app.include_router(websocket.router)
