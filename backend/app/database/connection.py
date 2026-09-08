"""Conexao e sessao do banco de dados.

SQLite e o padrao do MVP. Para PostgreSQL, basta trocar
NEKOMIND_DATABASE_URL - nenhuma outra mudanca de codigo e necessaria.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.models import Base


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    connect_args = {}
    if url.startswith("sqlite"):
        # Necessario para uso do SQLite pelo FastAPI em threads diferentes.
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Cria as tabelas (MVP sem Alembic; ver database/migrations/)."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """Dependency do FastAPI: fornece uma Session por requisicao."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager para uso fora de rotas (ex.: WebSocket)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
