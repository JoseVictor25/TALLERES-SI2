import logging
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.crud.crud_empleado import empleado as crud_empleado
from app.crud.crud_usuario import usuario as crud_usuario
from app.crud.crud_rol import rol as crud_rol
from app.crud.crud_rol_usuario import rol_usuario as crud_rol_usuario
from app.schemas.empleado import EmpleadoCreate, EmpleadoResponse, RolTallerEnum
from app.models.empleado import EstadoEmpleado
from typing import Optional
from app.crud.crud_persona import persona as crud_persona

logger = logging.getLogger(__name__)

async def create_empleado(
    db: AsyncSession,
    id_taller: int,
    data: EmpleadoCreate,
    id_usuario_actual: int  # el que crea, para verificar permisos
) -> EmpleadoResponse:
    # Verificar que el usuario actual tenga permiso (super_admin_taller en este taller)
    # (La verificación de permisos se hará en el endpoint usando require_permiso con taller específico)
    
    # 1. Buscar usuario por email
    persona = await crud_persona.get_by_email(db, data.email)
    if not persona:
        raise HTTPException(status_code=404, detail="Usuario no encontrado con ese email")
    usuario = await crud_usuario.get_by_id_persona(db, persona.id)
    if not usuario:
        raise HTTPException(status_code=404, detail="El email no tiene una cuenta de usuario asociada")
    # 2. Verificar que no esté ya empleado activo en este taller
    existing = await crud_empleado.get_active_by_usuario_taller(db, usuario.id, id_taller)
    if existing:
        raise HTTPException(status_code=400, detail="El usuario ya es empleado activo en este taller")
    
    # 3. Obtener el rol correspondiente
    ROL_MAP = {
        "admin_taller":       "Administrador del Taller",
        "super_admin_taller": "Administrador del Taller",
    }
    rol_nombre = ROL_MAP.get(data.rol.value, data.rol.value)

    rol = await crud_rol.get_by_nombre(db, rol_nombre)

    if not rol:
        raise HTTPException(status_code=500, detail=f"Rol {rol_nombre} no encontrado")
    
    # 4. Crear empleado (transacción)
    empleado_data = {
        "id_usuario": usuario.id,
        "id_taller": id_taller,
        "estado": EstadoEmpleado.activo,
    }
    nuevo_empleado = await crud_empleado.create(db, empleado_data)  # solo flush
    # Asignar rol en rol_usuario (si no lo tiene ya)
    # Verificar si ya tiene el rol en ese taller (podría ser que ya tenga otro rol)
    has_rol = await crud_rol_usuario.user_has_rol(db, usuario.id, rol.id, id_taller)
    if not has_rol:
        await crud_rol_usuario.add_rol(db, usuario.id, rol.id, id_taller)
    await db.commit()
    # Obtener el nombre del usuario
    return EmpleadoResponse(
        id=nuevo_empleado.id,
        usuario_id=usuario.id,
        usuario_nombre=usuario.nombre,
        usuario_email=persona.email,
        rol=rol_nombre,
        fecha_ingreso=nuevo_empleado.fecha_ingreso,
        fecha_salida=nuevo_empleado.fecha_salida,
        estado=nuevo_empleado.estado,
    )

async def list_empleados(
    db: AsyncSession,
    id_taller: int,
    estado: Optional[str],
    skip: int,
    limit: int
) -> tuple[list[EmpleadoResponse], int]:
    estado_enum = None
    if estado:
        try:
            estado_enum = EstadoEmpleado(estado)
        except ValueError:
            raise HTTPException(400, f"Estado inválido: {estado}")
    empleados, total = await crud_empleado.get_by_taller(db, id_taller, estado_enum, skip, limit)
    responses = []
    for emp in empleados:
        # Obtener la persona asociada al usuario
        persona = await crud_persona.get(db, emp.usuario.id_persona)
        # Obtener rol en el taller
        roles = await crud_rol_usuario.get_roles_by_usuario(db, emp.id_usuario)
        rol_nombre = None
        for r in roles:
            if r.id_taller == id_taller and r.rol.nombre in ["admin_taller", "super_admin_taller"]:
                rol_nombre = r.rol.nombre
                break
        responses.append(EmpleadoResponse(
            id=emp.id,
            usuario_id=emp.id_usuario,
            usuario_nombre=emp.usuario.nombre,
            usuario_email=persona.email,
            rol=rol_nombre,
            fecha_ingreso=emp.fecha_ingreso,
            fecha_salida=emp.fecha_salida,
            estado=emp.estado,
        ))
    return responses, total

async def suspender_empleado(
    db: AsyncSession,
    empleado_id: int,
    id_taller: int
) -> EmpleadoResponse:
    # 1. Suspende al empleado (el CRUD ahora devuelve el objeto con la relación cargada)
    empleado = await crud_empleado.suspend(db, empleado_id)
    if not empleado or empleado.id_taller != id_taller:
        raise HTTPException(404, "Empleado no encontrado en este taller")

    # 3. Ahora sí, accedemos a las relaciones de forma segura
    roles = await crud_rol_usuario.get_roles_by_usuario(db, empleado.id_usuario)
    roles_a_eliminar = [r for r in roles if r.id_taller == id_taller]
    for r in roles_a_eliminar:
        await crud_rol_usuario.remove_rol(db, r.id_usuario, r.id_rol, r.id_taller)

    # 2. Confirma la transacción
    await db.commit()

    persona = await crud_persona.get(db, empleado.usuario.id_persona)
    rol_nombre = roles_a_eliminar[0].rol.nombre if roles_a_eliminar else None

    return EmpleadoResponse(
        id=empleado.id,
        usuario_id=empleado.id_usuario,
        usuario_nombre=empleado.usuario.nombre,
        usuario_email=persona.email,
        rol=rol_nombre,
        fecha_ingreso=empleado.fecha_ingreso,
        fecha_salida=empleado.fecha_salida,
        estado=empleado.estado,
    )