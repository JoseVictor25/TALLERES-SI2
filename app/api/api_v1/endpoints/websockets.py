"""
WebSocket Endpoints
Tres canales de comunicación en tiempo real:
1. /ws/servicio/{id}  → estado del servicio
2. /ws/tracking/{id}  → GPS del técnico en vivo
3. /ws/taller/{id}    → notificaciones del taller
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.websocket_manager import manager
from datetime import datetime, timezone
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSockets"])


@router.websocket("/servicio/{servicio_id}")
async def ws_servicio(websocket: WebSocket, servicio_id: int, token: str = Query(default="")):
    """
    Canal de estado del servicio.
    - El cliente y el admin del taller se conectan aquí para recibir
      actualizaciones instantáneas cuando cambia el estado del servicio.
    - Mensajes salientes (del servidor):
      {"tipo": "estado_actualizado", "servicio_id": N, "estado": "en_camino", "timestamp": "..."}
      {"tipo": "servicio_info", "mensaje": "..."}
    """
    channel = f"servicio_{servicio_id}"
    await manager.connect(channel, websocket)

    try:
        # Enviar mensaje de bienvenida
        await manager.send_personal(websocket, {
            "tipo": "conexion_establecida",
            "canal": channel,
            "mensaje": f"Conectado al canal de servicio #{servicio_id}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Mantener la conexión abierta y escuchar mensajes (keepalive)
        while True:
            data = await websocket.receive_text()
            # El cliente puede enviar pings para mantener la conexión
            if data == "ping":
                await manager.send_personal(websocket, {"tipo": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)
        logger.info(f"Cliente desconectado del canal servicio_{servicio_id}")
    except Exception as e:
        manager.disconnect(channel, websocket)
        logger.error(f"Error en WS servicio_{servicio_id}: {e}")


@router.websocket("/tracking/{servicio_id}")
async def ws_tracking(websocket: WebSocket, servicio_id: int, token: str = Query(default="")):
    """
    Canal de tracking GPS en tiempo real.
    - El técnico envía su ubicación cada 5 segundos.
    - Los clientes conectados reciben la ubicación del técnico en tiempo real.
    - Mensajes entrantes (del técnico):
      {"tipo": "ubicacion", "lat": -17.78, "lon": -63.18}
    - Mensajes salientes (a los clientes):
      {"tipo": "ubicacion", "lat": -17.78, "lon": -63.18, "timestamp": "..."}
    """
    channel = f"tracking_{servicio_id}"
    await manager.connect(channel, websocket)

    try:
        await manager.send_personal(websocket, {
            "tipo": "conexion_establecida",
            "canal": channel,
            "mensaje": f"Conectado al tracking del servicio #{servicio_id}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await manager.send_personal(websocket, {"tipo": "pong"})
                continue

            try:
                mensaje = json.loads(data)

                if mensaje.get("tipo") == "ubicacion":
                    # Reenviar la ubicación a TODOS los conectados al canal
                    # (incluido el técnico, para confirmación)
                    broadcast_data = {
                        "tipo": "ubicacion",
                        "lat": mensaje.get("lat"),
                        "lon": mensaje.get("lon"),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    await manager.broadcast(channel, broadcast_data)

            except json.JSONDecodeError:
                await manager.send_personal(websocket, {
                    "tipo": "error",
                    "mensaje": "Formato JSON inválido"
                })

    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)
        logger.info(f"Desconectado del tracking servicio_{servicio_id}")
    except Exception as e:
        manager.disconnect(channel, websocket)
        logger.error(f"Error en WS tracking_{servicio_id}: {e}")


@router.websocket("/taller/{taller_id}")
async def ws_taller(websocket: WebSocket, taller_id: int, token: str = Query(default="")):
    """
    Canal de notificaciones del taller.
    - El admin del taller se conecta aquí para recibir:
      - Nuevas solicitudes de servicio
      - Respuestas a cotizaciones (aceptada/rechazada)
    - Mensajes salientes:
      {"tipo": "nueva_solicitud", "solicitud_id": N, "estado": "pendiente", ...}
      {"tipo": "cotizacion_respondida", "solicitud_id": N, "aceptada": true}
      {"tipo": "solicitud_rechazada", "solicitud_id": N}
    """
    channel = f"taller_{taller_id}"
    await manager.connect(channel, websocket)

    try:
        await manager.send_personal(websocket, {
            "tipo": "conexion_establecida",
            "canal": channel,
            "mensaje": f"Conectado a las notificaciones del taller #{taller_id}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_personal(websocket, {"tipo": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)
        logger.info(f"Desconectado del canal taller_{taller_id}")
    except Exception as e:
        manager.disconnect(channel, websocket)
        logger.error(f"Error en WS taller_{taller_id}: {e}")
