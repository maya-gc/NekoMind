"""Configuracoes centralizadas do backend NekoMind.

Valores podem vir de variaveis de ambiente ou do arquivo .env
(nunca versione o .env - use .env.example como referencia).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuracoes da aplicacao com defaults seguros para o MVP."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_prefix="NEKOMIND_",
        extra="ignore",
    )

    # MVP validado com SQLite local; outros bancos exigem outra estrategia de migracao.
    database_url: str = f"sqlite:///{BASE_DIR / 'storage' / 'nekomind.db'}"

    # Onde os arquivos de audio recebidos sao gravados.
    storage_dir: Path = BASE_DIR / "storage" / "audio"

    # Modo operacional: "demo" preserva simuladores identificados; "real" falha fechado.
    mode: Literal["demo", "real"] = "demo"

    # Adapters de IA: "mock" (padrao, offline e sem chave) ou implementacao real.
    asr_provider: Literal["mock", "faster_whisper"] = "mock"
    asr_model_size: str = Field(default="small", min_length=1)
    asr_device: Literal["cpu", "auto", "cuda"] = "cpu"
    asr_compute_type: Literal[
        "int8", "float32", "float16", "int8_float16", "int8_float32", "default", "auto"
    ] = "int8"
    llm_provider: Literal["mock", "local_keywords"] = "mock"

    # Serial e microfone sao configurados no CLI app.mac. PCM fixo em 16 kHz.
    serial_port: str = ""
    # Compatibilidade da interface de adaptadores; nenhum provedor atual exige chave.
    llm_api_key: str = ""

    host: str = "127.0.0.1"
    port: int = 8000

    @model_validator(mode="after")
    def validate_mode(self):
        if self.mode == "real" and (self.asr_provider == "mock" or self.llm_provider == "mock"):
            raise ValueError(
                "Modo real exige ASR e extracao implementados sem mock; configure explicitamente"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
