import logging
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from typing import Optional
from sqlalchemy import func
from datetime import datetime, timezone
from app.crud.crud_persona import persona as crud_persona
from app.crud.crud_empleado import empleado as crud_empleado
from app.crud.crud_usuario import usuario as crud_usuario
from app.crud.crud_rol import rol as crud_rol
from app.crud.crud_taller import taller as crud_taller
from app.crud.crud_rol_usuario import rol_usuario as crud_rol_usuario
from app.crud.crud_tecnico_especialidad import tecnico_especialidad
from app.crud.crud_especialidad import especialidad as crud_especialidad
from app.schemas.tecnico import TecnicoCreate, TecnicoResponse
from app.schemas.especialidad import EspecialidadResponse
from app.models.empleado import EstadoEmpleado
from app.core.constants import ROL_TECNICO  # asume constante 'tecnico'

logger = logging.getLogger(__name__)

async def create_tecnico(
    db: AsyncSession,
    taller_id: int,
    data: TecnicoCreate,
    id_usuario_actual: int,
) -> TecnicoResponse:
    # 1. Buscar usuario por email
    persona = await crud_persona.get_by_email(db, data.email)
    if not persona:
        raise HTTPException(404, "Usuario no encontrado con ese email")
    usuario = await crud_usuario.get_by_id_persona(db, persona.id)
    if not usuario:
        raise HTTPException(404, "El email no tiene cuenta de usuario")

    # 2. Verificar que no sea ya técnico activo en este taller
    existing_empleados, _ = await crud_empleado.get_tecnicos_by_taller(db, taller_id, EstadoEmpleado.disponible, 0, 1)
    if any(emp.id_usuario == usuario.id for emp in existing_empleados):
        raise HTTPException(400, "El usuario ya es técnico activo en este taller")

    # 3. Validar especialidades existentes
    especialidades = await crud_especialidad.get_multi_by_ids(db, data.especialidades_ids)  # implementar
    if len(especialidades) != len(data.especialidades_ids):
        raise HTTPException(400, "Alguna especialidad no existe")

    # 4. Crear empleado con estado 'disponible'
    empleado_data = {
        "id_usuario": usuario.id,
        "id_taller": taller_id,
        "estado": EstadoEmpleado.disponible,
    }
    nuevo_empleado = await crud_empleado.create(db, empleado_data)  # solo flush

    # 5. Asignar rol 'tecnico' y actualizar tenant_id
    rol_tecnico = await crud_rol.get_by_nombre(db, ROL_TECNICO)
    if not rol_tecnico:
        raise HTTPException(500, "Rol 'tecnico' no encontrado")
    has_rol = await crud_rol_usuario.user_has_rol(db, usuario.id, rol_tecnico.id, taller_id)
    if not has_rol:
        await crud_rol_usuario.add_rol(db, usuario.id, rol_tecnico.id, taller_id)
        
    taller_obj = await crud_taller.get(db, taller_id)
    if taller_obj and taller_obj.tenant_id:
        usuario.tenant_id = taller_obj.tenant_id

    # 6. Asignar especialidades
    for esp_id in data.especialidades_ids:
        await tecnico_especialidad.add(db, nuevo_empleado.id, esp_id)

    # 7. Commit
    await db.commit()

    # 8. Cargar especialidades para respuesta
    especialidades_resp = []
    for esp in especialidades:
        especialidades_resp.append(EspecialidadResponse(id=esp.id, nombre=esp.nombre, descripcion=esp.descripcion))

    return TecnicoResponse(
        id=nuevo_empleado.id,
        usuario_id=usuario.id,
        usuario_nombre=usuario.nombre,
        usuario_email=persona.email,
        estado=nuevo_empleado.estado,
        fecha_ingreso=nuevo_empleado.fecha_ingreso,
        fecha_salida=nuevo_empleado.fecha_salida,
        especialidades=especialidades_resp,
    )

async def list_tecnicos(
    db: AsyncSession,
    taller_id: int,
    estado: Optional[str],
    skip: int,
    limit: int
) -> tuple[list[TecnicoResponse], int]:
    estado_enum = None
    if estado:
        try:
            estado_enum = EstadoEmpleado(estado)
        except ValueError:
            raise HTTPException(400, f"Estado inválido: {estado}")

    empleados, total = await crud_empleado.get_tecnicos_by_taller(db, taller_id, estado_enum, skip, limit)

    responses = []
    for emp in empleados:
        # Obtener especialidades del técnico
        tec_esp = await tecnico_especialidad.get_by_empleado(db, emp.id)
        esp_ids = [t.id_especialidad for t in tec_esp]
        especialidades = await crud_especialidad.get_multi_by_ids(db, esp_ids)
        especialidades_resp = [EspecialidadResponse(id=e.id, nombre=e.nombre, descripcion=e.descripcion) for e in especialidades]

        # Obtener persona para email
        persona = await crud_persona.get(db, emp.usuario.id_persona)

        responses.append(TecnicoResponse(
            id=emp.id,
            usuario_id=emp.id_usuario,
            usuario_nombre=emp.usuario.nombre,
            usuario_email=persona.email,
            estado=emp.estado,
            fecha_ingreso=emp.fecha_ingreso,
            fecha_salida=emp.fecha_salida,
            especialidades=especialidades_resp,
        ))
    return responses, total

async def suspender_tecnico(
    db: AsyncSession,
    tecnico_id: int,
    taller_id: int
) -> TecnicoResponse:
    # 1. Obtener técnico con sus relaciones
    empleado = await crud_empleado.get_with_usuario(db, tecnico_id)  # implementar método con selectinload
    if not empleado or empleado.id_taller != taller_id:
        raise HTTPException(404, "Técnico no encontrado en este taller")
    if empleado.estado == EstadoEmpleado.suspendido:
        raise HTTPException(400, "El técnico ya está suspendido")

    # 2. Actualizar estado y fecha_salida
    empleado.estado = EstadoEmpleado.suspendido
    # Usar timestamp en Python para evitar cargas diferidas/refresh que requieren IO
    empleado.fecha_salida = datetime.now(timezone.utc)
    await db.flush()

    # 3. Eliminar rol 'tecnico' en este taller
    rol_tecnico = await crud_rol.get_by_nombre(db, ROL_TECNICO)
    if rol_tecnico:
        await crud_rol_usuario.remove_rol(db, empleado.id_usuario, rol_tecnico.id, taller_id)

    # 4. Commit
    await db.commit()

    # 5. Obtener datos para respuesta
    persona = await crud_persona.get(db, empleado.usuario.id_persona)
    # Especialidades (aunque suspendido, aún las mostramos)
    tec_esp = await tecnico_especialidad.get_by_empleado(db, empleado.id)
    esp_ids = [t.id_especialidad for t in tec_esp]
    especialidades = await crud_especialidad.get_multi_by_ids(db, esp_ids)
    especialidades_resp = [EspecialidadResponse(id=e.id, nombre=e.nombre, descripcion=e.descripcion) for e in especialidades]

    return TecnicoResponse(
        id=empleado.id,
        usuario_id=empleado.id_usuario,
        usuario_nombre=empleado.usuario.nombre,
        usuario_email=persona.email,
        estado=empleado.estado,
        fecha_ingreso=empleado.fecha_ingreso,
        fecha_salida=empleado.fecha_salida,
        especialidades=especialidades_resp,
    )


async def update_tecnico_especialidades(
    db: AsyncSession,
    taller_id: int,
    tecnico_id: int,
    especialidades_ids: list[int],
    id_usuario_actual: int,
) -> TecnicoResponse:
    """Reemplaza las especialidades de un técnico por la lista provista."""
    empleado = await crud_empleado.get_with_usuario(db, tecnico_id)
    if not empleado or empleado.id_taller != taller_id:
        raise HTTPException(404, "Técnico no encontrado en este taller")

    # Validar que todas las especialidades existan
    especialidades = await crud_especialidad.get_multi_by_ids(db, especialidades_ids)
    if len(especialidades) != len(especialidades_ids):
        raise HTTPException(400, "Alguna especialidad no existe")

    # Reemplazar relaciones: eliminar todas y volver a crear
    await tecnico_especialidad.remove_all_for_empleado(db, tecnico_id)
    for esp_id in especialidades_ids:
        await tecnico_especialidad.add(db, tecnico_id, esp_id)

    await db.commit()

    persona = await crud_persona.get(db, empleado.usuario.id_persona)
    especialidades_resp = [EspecialidadResponse(id=e.id, nombre=e.nombre, descripcion=e.descripcion) for e in especialidades]

    return TecnicoResponse(
        id=empleado.id,
        usuario_id=empleado.id_usuario,
        usuario_nombre=empleado.usuario.nombre,
        usuario_email=persona.email,
        estado=empleado.estado,
        fecha_ingreso=empleado.fecha_ingreso,
        fecha_salida=empleado.fecha_salida,
        especialidades=especialidades_resp,
    )