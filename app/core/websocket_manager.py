"""
WebSocket Connection Manager
Gestiona todas las conexiones WebSocket activas agrupadas por canal.
"""
from fastapi import WebSocket
from typing import Dict, List
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Administra conexiones WebSocket agrupadas por canales.
    
    Canales soportados:
    - servicio_{id}  → cambios de estado del servicio
    - tracking_{id}  → ubicación GPS en tiempo real del técnico
    - taller_{id}    → notificaciones para el admin del taller
    """

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, channel: str, websocket: WebSocket):
        """Acepta y registra una conexión WebSocket en un canal."""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        logger.info(f"WS conectado al canal '{channel}'. Total en canal: {len(self.active_connections[channel])}")

    def disconnect(self, channel: str, websocket: WebSocket):
        """Elimina una conexión WebSocket de un canal."""
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
            if len(self.active_connections[channel]) == 0:
                del self.active_connections[channel]
            logger.info(f"WS desconectado del canal '{channel}'.")

    async def broadcast(self, channel: str, data: dict):
        """Envía un mensaje JSON a todas las conexiones de un canal."""
        if channel not in self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(data)
            except Exception:
                dead_connections.append(connection)

        # Limpiar conexiones muertas
        for dead in dead_connections:
            self.disconnect(channel, dead)

    async def send_personal(self, websocket: WebSocket, data: dict):
        """Envía un mensaje JSON a una conexión específica."""
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    def get_connection_count(self, channel: str) -> int:
        """Devuelve el número de conexiones activas en un canal."""
        return len(self.active_connections.get(channel, []))


# Instancia global singleton
manager = ConnectionManager()
