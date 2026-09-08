"""Adaptador Wi-Fi (stub planejado).

Quando o firmware ganhar transporte Wi-Fi, este adapter recebera os
mesmos tipos de mensagem do protocolo JSON Lines via TCP/WebSocket
e os encaminhara para os servicos (audio_ingestion, session_analysis).

Por ora o WebSocket /ws/device (app/api/websocket.py) ja aceita
mensagens JSON no mesmo formato, servindo de ponto de entrada.
"""
from __future__ import annotations


class WifiAdapter:
    """Ponto de extensao: servidor TCP/WebSocket dedicado ao dispositivo."""

    def start(self) -> None:  # pragma: no cover - nao implementado
        raise NotImplementedError("transporte Wi-Fi planejado para versao futura")
