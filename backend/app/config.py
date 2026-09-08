"""Configuracoes centralizadas do backend NekoMind.

Valores podem vir de variaveis de ambiente ou do arquivo .env
(nunca versione o .env - use .env.example como referencia).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuracoes da aplicacao com defaults seguros para o MVP."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_prefix="NEKOMIND_",
        extra="ignore",
    )

    # Banco: SQLite local por padrao; para PostgreSQL use, por exemplo:
    # NEKOMIND_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/nekomind
    database_url: str = f"sqlite:///{BASE_DIR / 'storage' / 'nekomind.db'}"

    # Onde os arquivos de audio recebidos sao gravados.
    storage_dir: Path = BASE_DIR / "storage" / "audio"

    # Adapters de IA: "mock" (padrao, offline e sem chave) ou implementacao real.
    asr_provider: str = "mock"  # futuro: "faster_whisper"
    llm_provider: str = "mock"  # futuro: "openai" / outra API

    # Chave da API de LLM - NUNCA versionar; definida via .env/ambiente.
    llm_api_key: str = ""

    # Serial (futuro): porta do dispositivo ESP32-S3 (ex.: COM5, /dev/ttyACM0).
    serial_port: str = ""
    serial_baudrate: int = 115200

    host: str = "127.0.0.1"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
