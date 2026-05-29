"""
CU-14: Gestionar Comunicación
Endpoints de mensajería interna entre cliente y taller por servicio.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from pydantic import BaseModel, Field
from datetime import datetime

from app.db.session import get_db
from app.core.deps import get_current_usuario
from app.models.usuario import Usuario
from app.models.servicio import Servicio
from app.models.solicitud_servicio import SolicitudServicio
from app.models.diagnostico import Diagnostico
from app.models.solicitud_diagnostico import SolicitudDiagnostico
from app.models.persona import Persona
from app.models.mensaje import Mensaje
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol
from app.models.empleado import Empleado

router = APIRouter(prefix="/mensajes", tags=["Comunicación"])


# ============================================================
# SCHEMAS
# ============================================================

class MensajeCreate(BaseModel):
    texto: str = Field(..., min_length=1, max_length=2000, description="Contenido del mensaje")

class MensajeResponse(BaseModel):
    id: int
    texto: str
    tiempo: datetime
    leido: bool
    id_remitente: Optional[int] = None
    nombre_remitente: Optional[str] = None
    es_mio: bool = False  # True si el mensaje lo envió el usuario autenticado

class ConversacionResponse(BaseModel):
    id_servicio: int
    total_mensajes: int
    mensajes_no_leidos: int
    mensajes: List[MensajeResponse]


# ============================================================
# HELPERS
# ============================================================

async def _verificar_acceso_servicio(
    db: AsyncSession,
    servicio: Servicio,
    usuario_id: int
) -> str:
    """
    Verifica que el usuario tiene acceso al servicio.
    Retorna el rol: "cliente", "tecnico", "admin_taller" o lanza 403.
    """
    # ¿Es el cliente?
    if servicio.id_solicitud_servicio:
        solicitud = await db.get(SolicitudServicio, servicio.id_solicitud_servicio)
        if solicitud:
            diagnostico = await db.get(Diagnostico, solicitud.id_diagnostico)
            if diagnostico:
                sol_diag = await db.get(SolicitudDiagnostico, diagnostico.id_solicitud_diagnostico)
                if sol_diag:
                    persona = await db.get(Persona, sol_diag.id_persona)
                    if persona:
                        result = await db.execute(
                            select(Usuario).where(Usuario.id_persona == persona.id)
                        )
                        usuario_cliente = result.scalar_one_or_none()
                        if usuario_cliente and usuario_cliente.id == usuario_id:
                            return "cliente"

    # ¿Es admin o técnico del taller?
    result = await db.execute(
        select(RolUsuario).join(Rol).where(
            and_(
                RolUsuario.id_usuario == usuario_id,
                RolUsuario.id_taller == servicio.id_taller,
                Rol.nombre.in_([ROL_ADMIN_TALLER, ROL_TECNICO])
            )
        )
    )
    rol_usuario = result.scalar_one_or_none()
    if rol_usuario:
        result_rol = await db.execute(
            select(Rol).where(Rol.id == rol_usuario.id_rol)
        )
        rol = result_rol.scalar_one_or_none()
        if rol:
            return "admin_taller" if rol.nombre == ROL_ADMIN_TALLER else "tecnico"

    raise HTTPException(
        status_code=403,
        detail="No tienes acceso a este servicio"
    )


async def _obtener_nombre_remitente(db: AsyncSession, usuario_id: int) -> str:
    """Obtiene el nombre legible del remitente"""
    usuario = await db.get(Usuario, usuario_id)
    if not usuario:
        return "Usuario"
    persona = await db.get(Persona, usuario.id_persona)
    if not persona:
        return f"Usuario #{usuario_id}"
    return persona.nombre


# ============================================================
# ENDPOINTS
# ============================================================

@router.post(
    "/servicio/{servicio_id}",
    response_model=MensajeResponse,
    status_code=status.HTTP_201_CREATED
)
async def enviar_mensaje(
    servicio_id: int,
    payload: MensajeCreate,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [CLIENTE / TALLER] Envía un mensaje en la conversación de un servicio.
    Solo pueden enviar mensajes el cliente del servicio y el personal del taller.
    """
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    # Verificar acceso (lanza 403 si no tiene acceso)
    await _verificar_acceso_servicio(db, servicio, current_usuario.id)

    # No permitir mensajes en servicios finalizados o cancelados
    if servicio.estado.value in ("finalizado", "cancelado"):
        raise HTTPException(
            status_code=400,
            detail="No se pueden enviar mensajes en un servicio finalizado o cancelado"
        )

    nuevo_mensaje = Mensaje(
        id_servicio=servicio_id,
        id_remitente=current_usuario.id,
        texto=payload.texto.strip()
    )
    db.add(nuevo_mensaje)
    await db.commit()
    await db.refresh(nuevo_mensaje)

    nombre = await _obtener_nombre_remitente(db, current_usuario.id)

    return MensajeResponse(
        id=nuevo_mensaje.id,
        texto=nuevo_mensaje.texto,
        tiempo=nuevo_mensaje.tiempo,
        leido=nuevo_mensaje.leido,
        id_remitente=nuevo_mensaje.id_remitente,
        nombre_remitente=nombre,
        es_mio=True
    )


@router.get("/servicio/{servicio_id}", response_model=ConversacionResponse)
async def listar_mensajes(
    servicio_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [CLIENTE / TALLER] Lista todos los mensajes de la conversación de un servicio.
    Marca automáticamente como leídos los mensajes que NO fueron enviados por el usuario actual.
    """
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    await _verificar_acceso_servicio(db, servicio, current_usuario.id)

    # Obtener mensajes ordenados cronológicamente
    result = await db.execute(
        select(Mensaje)
        .where(Mensaje.id_servicio == servicio_id)
        .order_by(Mensaje.tiempo.asc())
    )
    mensajes_db = result.scalars().all()

    # Marcar como leídos los mensajes que no son míos y estaban sin leer
    ids_a_marcar = [
        m.id for m in mensajes_db
        if m.id_remitente != current_usuario.id and not m.leido
    ]
    if ids_a_marcar:
        await db.execute(
            update(Mensaje)
            .where(Mensaje.id.in_(ids_a_marcar))
            .values(leido=True)
        )
        await db.commit()

    # Construir respuesta
    mensajes_response = []
    no_leidos_total = 0

    for m in mensajes_db:
        nombre = await _obtener_nombre_remitente(db, m.id_remitente) if m.id_remitente else "Desconocido"
        leido_final = True if m.id in ids_a_marcar else m.leido

        if not leido_final and m.id_remitente != current_usuario.id:
            no_leidos_total += 1

        mensajes_response.append(MensajeResponse(
            id=m.id,
            texto=m.texto,
            tiempo=m.tiempo,
            leido=leido_final,
            id_remitente=m.id_remitente,
            nombre_remitente=nombre,
            es_mio=(m.id_remitente == current_usuario.id)
        ))

    return ConversacionResponse(
        id_servicio=servicio_id,
        total_mensajes=len(mensajes_response),
        mensajes_no_leidos=no_leidos_total,
        mensajes=mensajes_response
    )


@router.put("/servicio/{servicio_id}/marcar-leidos", status_code=status.HTTP_200_OK)
async def marcar_mensajes_leidos(
    servicio_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [CLIENTE / TALLER] Marca como leídos todos los mensajes del servicio
    que NO fueron enviados por el usuario actual.
    """
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    await _verificar_acceso_servicio(db, servicio, current_usuario.id)

    result = await db.execute(
        update(Mensaje)
        .where(
            and_(
                Mensaje.id_servicio == servicio_id,
                Mensaje.id_remitente != current_usuario.id,
                Mensaje.leido == False
            )
        )
        .values(leido=True)
    )
    await db.commit()

    actualizados = result.rowcount
    return {
        "mensaje": f"{actualizados} mensaje(s) marcado(s) como leído(s)",
        "id_servicio": servicio_id
    }


@router.get("/servicio/{servicio_id}/no-leidos", status_code=status.HTTP_200_OK)
async def contar_mensajes_no_leidos(
    servicio_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [CLIENTE / TALLER] Devuelve el número de mensajes no leídos en el servicio.
    Endpoint ligero, ideal para badges/notificaciones en el frontend.
    """
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    await _verificar_acceso_servicio(db, servicio, current_usuario.id)

    result = await db.execute(
        select(Mensaje).where(
            and_(
                Mensaje.id_servicio == servicio_id,
                Mensaje.id_remitente != current_usuario.id,
                Mensaje.leido == False
            )
        )
    )
    no_leidos = len(result.scalars().all())

    return {
        "id_servicio": servicio_id,
        "mensajes_no_leidos": no_leidos
    }
