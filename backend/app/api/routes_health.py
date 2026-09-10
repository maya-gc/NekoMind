"""Health check do backend."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "nekomind-backend",
        "mode": settings.mode,
        "asr_provider": settings.asr_provider,
        "llm_provider": settings.llm_provider,
    }
