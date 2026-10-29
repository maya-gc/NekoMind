"""Esboco legado, fora do caminho MVP touch + Mac.

O bridge executavel esta em app.mac; /ws/device legado foi desativado.
Esta classe nao comprova integracao de hardware nem recebe audio no MVP.
"""

from __future__ import annotations


class WifiAdapter:
    """Ponto de extensao: servidor TCP/WebSocket dedicado ao dispositivo."""

    def start(self) -> None:  # pragma: no cover - nao implementado
        raise NotImplementedError("transporte Wi-Fi planejado para versao futura")
