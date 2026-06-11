"""
Servicio para envío de notificaciones push usando Firebase Admin SDK (FCM v1)
"""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import os

import firebase_admin
from firebase_admin import credentials, messaging

from app.models.dispositivo_usuario import DispositivoUsuario
from app.models.persona import Persona
from app.models.servicio import Servicio
from app.models.solicitud_servicio import SolicitudServicio
from app.models.solicitud_diagnostico import SolicitudDiagnostico
from app.models.diagnostico import Diagnostico
from app.crud import crud_dispositivo_usuario
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Firebase Admin
try:
    if not firebase_admin._apps:
        # Buscamos el archivo JSON generado
        cred_path = os.path.join(os.getcwd(), 'talleres.json')
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin inicializado exitosamente.")
        else:
            logger.warning(f"No se encontró el archivo de credenciales de Firebase en {cred_path}")
except Exception as e:
    logger.error(f"Error inicializando Firebase Admin: {e}")

class NotificationService:
    """Servicio para gestionar notificaciones push"""
    
    async def enviar_notificacion_push(
        self,
        tokens: List[str],
        titulo: str,
        mensaje: str,
        datos_extra: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Envía notificación push a una lista de tokens FCM usando Firebase Admin
        """
        if not firebase_admin._apps:
            logger.warning("Firebase Admin no está inicializado, no se pueden enviar notificaciones")
            return False
        
        if not tokens:
            logger.info("No hay tokens FCM para enviar notificación")
            return True
        
        # En FCM v1, los datos adicionales (data payload) deben ser un diccionario de strings
        if datos_extra:
            datos_extra = {k: str(v) for k, v in datos_extra.items()}
            
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=titulo,
                body=mensaje,
            ),
            data=datos_extra,
            tokens=tokens
        )
        
        try:
            # Enviar notificación a multiples tokens (esto es bloqueante, pero muy rápido)
            # Idealmente se correría en un threadpool (run_in_threadpool) si es muy pesado
            response = messaging.send_each_for_multicast(message)
            
            logger.info(f"Notificación enviada: {response.success_count} éxitos, {response.failure_count} fallos")
            
            if response.failure_count > 0:
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        logger.warning(f"Error enviando a token {tokens[idx]}: {resp.exception}")
                        
            return response.success_count > 0
                    
        except Exception as e:
            logger.error(f"Error enviando notificación FCM: {e}")
            return False
    
    async def obtener_tokens_persona(self, db: AsyncSession, id_persona: int) -> List[str]:
        """
        Obtiene todos los tokens FCM de una persona
        """
        dispositivos = await crud_dispositivo_usuario.dispositivo_usuario.get_by_persona(db, id_persona)
        return [d.token_fcm for d in dispositivos if d.token_fcm]
    
    async def notificar_solicitud_aceptada(
        self,
        db: AsyncSession,
        servicio: Servicio
    ) -> bool:
        """
        Notifica al cliente que su solicitud fue aceptada
        """
        try:
            # Obtener datos del cliente
            result = await db.execute(
                select(SolicitudDiagnostico, Persona).join(
                    Diagnostico, SolicitudDiagnostico.id == Diagnostico.id_solicitud_diagnostico
                ).join(
                    SolicitudServicio, Diagnostico.id == SolicitudServicio.id_diagnostico
                ).join(
                    Persona, SolicitudDiagnostico.id_persona == Persona.id
                ).where(
                    SolicitudServicio.id == servicio.id_solicitud_servicio
                )
            )
            
            row = result.first()
            if not row:
                logger.warning(f"No se encontró cliente para servicio {servicio.id}")
                return False
            
            solicitud_diag, persona = row
            
            # Obtener tokens FCM del cliente
            tokens = await self.obtener_tokens_persona(db, persona.id)
            
            if not tokens:
                logger.info(f"Cliente {persona.id} no tiene tokens FCM registrados")
                return True
            
            # Enviar notificación
            titulo = "¡Solicitud Aceptada!"
            mensaje = f"Un taller ha aceptado tu solicitud de servicio. El técnico está en camino."
            
            datos_extra = {
                "tipo": "solicitud_aceptada",
                "servicio_id": str(servicio.id),
                "accion": "abrir_servicio_detalle"
            }
            
            return await self.enviar_notificacion_push(tokens, titulo, mensaje, datos_extra)
            
        except Exception as e:
            logger.error(f"Error notificando solicitud aceptada: {e}")
            return False
    
    async def notificar_cambio_estado_servicio(
        self,
        db: AsyncSession,
        servicio: Servicio,
        estado_anterior: str,
        estado_nuevo: str
    ) -> bool:
        """
        Notifica al cliente sobre cambios de estado del servicio
        """
        try:
            # Obtener datos del cliente
            result = await db.execute(
                select(SolicitudDiagnostico, Persona).join(
                    Diagnostico, SolicitudDiagnostico.id == Diagnostico.id_solicitud_diagnostico
                ).join(
                    SolicitudServicio, Diagnostico.id == SolicitudServicio.id_diagnostico
                ).join(
                    Persona, SolicitudDiagnostico.id_persona == Persona.id
                ).where(
                    SolicitudServicio.id == servicio.id_solicitud_servicio
                )
            )
            
            row = result.first()
            if not row:
                return False
            
            solicitud_diag, persona = row
            
            # Obtener tokens FCM del cliente
            tokens = await self.obtener_tokens_persona(db, persona.id)
            
            if not tokens:
                return True
            
            # Generar mensaje según el estado
            titulo, mensaje = self._generar_mensaje_estado(estado_nuevo)
            
            datos_extra = {
                "tipo": "cambio_estado_servicio",
                "servicio_id": str(servicio.id),
                "estado_anterior": estado_anterior,
                "estado_nuevo": estado_nuevo,
                "accion": "abrir_servicio_detalle"
            }
            
            return await self.enviar_notificacion_push(tokens, titulo, mensaje, datos_extra)
            
        except Exception as e:
            logger.error(f"Error notificando cambio de estado: {e}")
            return False
    
    async def notificar_servicio_finalizado(
        self,
        db: AsyncSession,
        servicio: Servicio
    ) -> bool:
        """
        Notifica al cliente que su servicio ha sido finalizado
        """
        try:
            # Obtener datos del cliente
            result = await db.execute(
                select(SolicitudDiagnostico, Persona).join(
                    Diagnostico, SolicitudDiagnostico.id == Diagnostico.id_solicitud_diagnostico
                ).join(
                    SolicitudServicio, Diagnostico.id == SolicitudServicio.id_diagnostico
                ).join(
                    Persona, SolicitudDiagnostico.id_persona == Persona.id
                ).where(
                    SolicitudServicio.id == servicio.id_solicitud_servicio
                )
            )
            
            row = result.first()
            if not row:
                return False
            
            solicitud_diag, persona = row
            
            # Obtener tokens FCM del cliente
            tokens = await self.obtener_tokens_persona(db, persona.id)
            
            if not tokens:
                return True
            
            # Enviar notificación
            titulo = "¡Servicio Completado!"
            mensaje = "Tu servicio ha sido finalizado exitosamente. ¡No olvides valorar tu experiencia!"
            
            datos_extra = {
                "tipo": "servicio_finalizado",
                "servicio_id": str(servicio.id),
                "accion": "abrir_valoracion"
            }
            
            return await self.enviar_notificacion_push(tokens, titulo, mensaje, datos_extra)
            
        except Exception as e:
            logger.error(f"Error notificando servicio finalizado: {e}")
            return False
            
    async def notificar_cotizacion_recibida(
        self,
        db: AsyncSession,
        id_solicitud: int,
        costo_estimado: float
    ) -> bool:
        """
        Notifica al cliente que un taller ha respondido con una cotización
        """
        try:
            from app.models.taller import Taller
            
            # Obtener datos del cliente y del taller a partir de la solicitud
            result = await db.execute(
                select(SolicitudDiagnostico, Persona, Diagnostico.id, Taller.nombre).join(
                    Diagnostico, SolicitudDiagnostico.id == Diagnostico.id_solicitud_diagnostico
                ).join(
                    SolicitudServicio, Diagnostico.id == SolicitudServicio.id_diagnostico
                ).join(
                    Persona, SolicitudDiagnostico.id_persona == Persona.id
                ).outerjoin(
                    Taller, SolicitudServicio.id_taller == Taller.id
                ).where(
                    SolicitudServicio.id == id_solicitud
                )
            )
            
            row = result.first()
            if not row:
                logger.warning(f"No se encontró cliente para solicitud de servicio {id_solicitud}")
                return False
            
            solicitud_diag, persona, diagnostico_id, nombre_taller = row
            nombre_taller = nombre_taller or "Un taller"
            
            # Obtener tokens FCM del cliente
            tokens = await self.obtener_tokens_persona(db, persona.id)
            
            if not tokens:
                logger.info(f"Cliente {persona.id} no tiene tokens FCM registrados")
                return True
            
            # Enviar notificación
            titulo = f"¡{nombre_taller} te envió una cotización!"
            mensaje = f"{nombre_taller} ha cotizado tu servicio por Bs {costo_estimado}. Revisa los detalles y decide."
            
            datos_extra = {
                "tipo": "solicitud_cotizada",
                "solicitud_id": str(id_solicitud),
                "diagnostico_id": str(diagnostico_id),
                "costo_estimado": str(costo_estimado),
                "nombre_taller": nombre_taller,
                "accion": "abrir_cotizacion_detalle"
            }
            
            return await self.enviar_notificacion_push(tokens, titulo, mensaje, datos_extra)
            
        except Exception as e:
            logger.error(f"Error notificando cotización recibida: {e}")
            return False
    
    def _generar_mensaje_estado(self, estado: str) -> tuple[str, str]:
        """
        Genera título y mensaje según el estado del servicio
        """
        mensajes = {
            "tecnico_asignado": (
                "Técnico Asignado",
                "Se ha asignado un técnico a tu servicio"
            ),
            "en_camino": (
                "Técnico en Camino",
                "El técnico está en camino hacia tu ubicación"
            ),
            "en_lugar": (
                "Técnico en el Lugar",
                "El técnico ha llegado a tu ubicación"
            ),
            "en_atencion": (
                "Servicio en Atención",
                "El técnico está trabajando en tu vehículo"
            ),
            "finalizado": (
                "¡Servicio Completado!",
                "Tu servicio ha sido finalizado exitosamente"
            ),
            "cancelado": (
                "Servicio Cancelado",
                "Tu servicio ha sido cancelado"
            )
        }
        
        return mensajes.get(estado, ("Actualización de Servicio", f"Tu servicio cambió a: {estado}"))

# Instancia global del servicio
notification_service = NotificationService()