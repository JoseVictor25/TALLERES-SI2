from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.schemas.taller import TallerResponse, TallerDetailResponse, TallerUpdate
from app.crud.crud_taller import taller as crud_taller
from app.crud.crud_rol import rol as crud_rol
from app.crud.crud_rol_usuario import rol_usuario as crud_rol_usuario
from geoalchemy2.shape import to_shape
from geoalchemy2 import WKTElement
from app.models.taller import EstadoTaller, Taller
from app.core.constants import ROL_ADMIN_TALLER, ROL_SUPER_ADMIN_TALLER
from datetime import time as datetime_time


def _format_ubicacion(geog) -> str:
    """Convierte un objeto Geography a string 'lat,lon'."""
    if geog is None:
        return ""
    point = to_shape(geog)
    return f"{point.y},{point.x}"


def _format_time(t) -> Optional[str]:
    """Convierte un objeto time a string 'HH:MM:SS'."""
    if t is None:
        return None
    if isinstance(t, datetime_time):
        return t.strftime("%H:%M:%S")
    return str(t)


def _parse_time(time_str: str) -> datetime_time:
    """Convierte string 'HH:MM' o 'HH:MM:SS' a objeto time."""
    parts = time_str.split(':')
    if len(parts) == 2:
        return datetime_time(int(parts[0]), int(parts[1]), 0)
    elif len(parts) == 3:
        return datetime_time(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        raise ValueError("Formato de hora inválido. Use HH:MM o HH:MM:SS")


async def _check_user_taller_role(
    db: AsyncSession,
    id_usuario: int,
    id_taller: int,
    required_roles: List[str]
) -> str:
    """
    Verifica que el usuario tenga uno de los roles requeridos en el taller específico.
    Retorna el rol que tiene el usuario.
    Lanza HTTPException si no tiene permisos.
    """
    for rol_nombre in required_roles:
        rol = await crud_rol.get_by_nombre(db, rol_nombre)
        if rol:
            has_role = await crud_rol_usuario.user_has_rol(
                db, id_usuario, rol.id, id_taller
            )
            if has_role:
                return rol_nombre
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tiene permisos para acceder a este taller"
    )


async def list_mis_talleres(
    db: AsyncSession,
    id_usuario: int,
    skip: int = 0,
    limit: int = 10
) -> Tuple[List[TallerResponse], int]:
    talleres, total = await crud_taller.get_by_usuario_admin(db, id_usuario, skip, limit)
    responses = []
    for t in talleres:
        responses.append(TallerResponse(
            id=t.id,
            nombre=t.nombre,
            telefono=t.telefono,
            email=t.email,
            ubicacion=_format_ubicacion(t.ubicacion),
            estado=t.estado
        ))
    return responses, total


async def get_taller_detail(
    db: AsyncSession,
    id_taller: int,
    id_usuario: int
) -> TallerDetailResponse:
    """
    Obtiene el detalle completo de un taller.
    Verifica que el usuario sea admin_taller o super_admin_taller del taller.
    """
    # Verificar que el taller existe
    taller_obj = await crud_taller.get(db, id_taller)
    if not taller_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Taller no encontrado"
        )
    
    # Verificar permisos (admin_taller o super_admin_taller)
    await _check_user_taller_role(
        db, id_usuario, id_taller,
        [ROL_ADMIN_TALLER, ROL_SUPER_ADMIN_TALLER]
    )
    
    return TallerDetailResponse(
        id=taller_obj.id,
        nombre=taller_obj.nombre,
        telefono=taller_obj.telefono,
        email=taller_obj.email,
        ubicacion=_format_ubicacion(taller_obj.ubicacion),
        hora_inicio=_format_time(taller_obj.hora_inicio),
        hora_fin=_format_time(taller_obj.hora_fin),
        url_web=taller_obj.url_web,
        puntos=float(taller_obj.puntos) if taller_obj.puntos else 0.0,
        estado=taller_obj.estado.value if isinstance(taller_obj.estado, EstadoTaller) else str(taller_obj.estado)
    )


async def update_taller(
    db: AsyncSession,
    id_taller: int,
    id_usuario: int,
    data: TallerUpdate
) -> TallerDetailResponse:
    """
    Actualiza la información de un taller.
    Solo super_admin_taller puede editar.
    """
    # Verificar que el taller existe
    taller_obj = await crud_taller.get(db, id_taller)
    if not taller_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Taller no encontrado"
        )
    
    # Verificar que el usuario es super_admin_taller del taller
    await _check_user_taller_role(
        db, id_usuario, id_taller,
        [ROL_SUPER_ADMIN_TALLER]
    )
    
    # Preparar datos para actualizar
    update_data = {}
    
    if data.nombre is not None:
        # Verificar que el nombre no esté en uso por otro taller
        existing = await crud_taller.get_by_nombre(db, data.nombre)
        if existing and existing.id != id_taller:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe otro taller con ese nombre"
            )
        update_data['nombre'] = data.nombre
    
    if data.telefono is not None:
        update_data['telefono'] = data.telefono
    
    if data.email is not None:
        update_data['email'] = data.email
    
    if data.ubicacion is not None and data.ubicacion.strip():
        # Convertir "lat,lon" a Geography
        parts = data.ubicacion.split(',')
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
        # Crear punto en formato WKT (Well-Known Text)
        wkt_point = f'POINT({lon} {lat})'
        update_data['ubicacion'] = WKTElement(wkt_point, srid=4326)
    
    if data.hora_inicio is not None:
        try:
            update_data['hora_inicio'] = _parse_time(data.hora_inicio)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hora de inicio inválida: {str(e)}"
            )
    
    if data.hora_fin is not None:
        try:
            update_data['hora_fin'] = _parse_time(data.hora_fin)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hora de fin inválida: {str(e)}"
            )
    
    # Validar que hora_fin > hora_inicio si ambas están presentes
    hora_inicio = update_data.get('hora_inicio', taller_obj.hora_inicio)
    hora_fin = update_data.get('hora_fin', taller_obj.hora_fin)
    if hora_inicio and hora_fin and hora_fin <= hora_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La hora de fin debe ser posterior a la hora de inicio"
        )
    
    if data.url_web is not None:
        update_data['url_web'] = data.url_web if data.url_web.strip() else None
    
    # Actualizar el taller
    if update_data:
        updated = await crud_taller.update(db, taller_obj, update_data)
        await db.commit()
        await db.refresh(updated)
    else:
        updated = taller_obj
    
    return TallerDetailResponse(
        id=updated.id,
        nombre=updated.nombre,
        telefono=updated.telefono,
        email=updated.email,
        ubicacion=_format_ubicacion(updated.ubicacion),
        hora_inicio=_format_time(updated.hora_inicio),
        hora_fin=_format_time(updated.hora_fin),
        url_web=updated.url_web,
        puntos=float(updated.puntos) if updated.puntos else 0.0,
        estado=updated.estado.value if isinstance(updated.estado, EstadoTaller) else str(updated.estado)
    )


async def list_all_talleres_admin(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    estado: Optional[str] = None
) -> Tuple[List[TallerResponse], int]:
    """Listado paginado para panel admin (todos los talleres), opcionalmente filtra por estado."""
    estado_enum: Optional[EstadoTaller] = None
    if estado:
        try:
            estado_enum = EstadoTaller(estado)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado inválido")

    from sqlalchemy.orm import selectinload
    from app.models.solicitud_afiliacion import SolicitudAfiliacion
    from app.models.usuario import Usuario

    load_opts = [
        selectinload(Taller.solicitud).selectinload(SolicitudAfiliacion.usuario_solicita).selectinload(Usuario.persona)
    ]

    talleres, total = await crud_taller.get_paginated(db, skip=skip, limit=limit, estado=estado_enum, load_options=load_opts)
    responses = []
    for t in talleres:
        creador_nom = None
        creador_em = None
        if t.solicitud and t.solicitud.usuario_solicita and t.solicitud.usuario_solicita.persona:
            p = t.solicitud.usuario_solicita.persona
            creador_nom = f"{p.nombre or ''} {p.apellido_p or ''}".strip()
            creador_em = p.email

        responses.append(TallerResponse(
            id=t.id,
            nombre=t.nombre,
            telefono=t.telefono,
            email=t.email,
            ubicacion=_format_ubicacion(t.ubicacion),
            estado=t.estado.value if isinstance(t.estado, EstadoTaller) else str(t.estado),
            creador_nombre=creador_nom,
            creador_email=creador_em
        ))
    return responses, total


async def suspend_taller(db: AsyncSession, id_taller: int) -> TallerResponse:
    obj = await crud_taller.get(db, id_taller)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taller no encontrado")
    if obj.estado == EstadoTaller.suspendido:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Taller ya está suspendido")
    updated = await crud_taller.update(db, obj, {"estado": EstadoTaller.suspendido})
    await db.commit()
    return TallerResponse(id=updated.id, nombre=updated.nombre, telefono=updated.telefono, email=updated.email, ubicacion=_format_ubicacion(updated.ubicacion), estado=updated.estado.value)


async def activar_taller(db: AsyncSession, id_taller: int) -> TallerResponse:
    obj = await crud_taller.get(db, id_taller)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taller no encontrado")
    if obj.estado == EstadoTaller.activo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Taller ya está activo")
    updated = await crud_taller.update(db, obj, {"estado": EstadoTaller.activo})
    await db.commit()
    return TallerResponse(id=updated.id, nombre=updated.nombre, telefono=updated.telefono, email=updated.email, ubicacion=_format_ubicacion(updated.ubicacion), estado=updated.estado.value)