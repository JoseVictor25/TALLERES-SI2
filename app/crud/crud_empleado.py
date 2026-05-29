from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.crud.base import CRUDBase
from app.models.empleado import Empleado, EstadoEmpleado
from sqlalchemy.orm import selectinload
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol
from app.models.tecnico_especialidad import TecnicoEspecialidad
from app.core.constants import ROL_TECNICO

class CRUDEmpleado(CRUDBase[Empleado]):
    async def get_by_taller(
        self,
        db: AsyncSession,
        id_taller: int,
        estado: Optional[EstadoEmpleado] = None,
        skip: int = 0,
        limit: int = 10
    ) -> Tuple[List[Empleado], int]:
        query = select(Empleado).where(Empleado.id_taller == id_taller).options(selectinload(Empleado.usuario))
        if estado:
            query = query.where(Empleado.estado == estado)
        total_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total = total_result.scalar_one()
        query = query.offset(skip).limit(limit).order_by(Empleado.fecha_ingreso.desc())
        result = await db.execute(query)
        items = result.scalars().all()
        return items, total

    async def suspend(self, db: AsyncSession, id: int) -> Optional[Empleado]:
        # 1. Obtén el empleado y carga su relación 'usuario' con selectinload
        stmt = select(Empleado).where(Empleado.id == id).options(selectinload(Empleado.usuario))
        result = await db.execute(stmt)
        empleado = result.scalar_one_or_none()

        if empleado and empleado.estado != EstadoEmpleado.suspendido:
            # 2. Actualiza el estado y la fecha de salida
            empleado.estado = EstadoEmpleado.suspendido
            empleado.fecha_salida = func.now()
            await db.flush()  # Sincroniza los cambios con la BD pero no los confirma
            await db.refresh(empleado)  # Recarga el objeto (ahora incluye la relación 'usuario')
        return empleado

    async def get_active_by_usuario_taller(self, db: AsyncSession, id_usuario: int, id_taller: int) -> Optional[Empleado]:
        result = await db.execute(
            select(Empleado).where(
                Empleado.id_usuario == id_usuario,
                Empleado.id_taller == id_taller,
                Empleado.estado.in_([EstadoEmpleado.activo, EstadoEmpleado.disponible, EstadoEmpleado.en_servicio])
            )
        )
        return result.scalar_one_or_none()
    
    # Añadir en CRUDEmpleado
    async def get_tecnicos_by_taller(
        self,
        db: AsyncSession,
        id_taller: int,
        estado: Optional[EstadoEmpleado] = None,
        skip: int = 0,
        limit: int = 10
    ) -> Tuple[List[Empleado], int]:

        # Subconsulta para obtener ids de usuarios con rol tecnico en ese taller
        subq_usuario = select(RolUsuario.id_usuario).join(Rol).where(
            RolUsuario.id_taller == id_taller,
            Rol.nombre == ROL_TECNICO
        ).subquery()

        # Subconsulta para obtener ids de empleados que tienen especialidades (fueron técnicos)
        subq_empleado_from_tecnico = select(TecnicoEspecialidad.id_empleado).subquery()

        # Incluir empleados que actualmente tienen el rol 'tecnico' OR que tienen entradas en tecnico_especialidad
        query = select(Empleado).where(
            Empleado.id_taller == id_taller,
            or_(Empleado.id_usuario.in_(subq_usuario), Empleado.id.in_(subq_empleado_from_tecnico))
        ).options(selectinload(Empleado.usuario))

        if estado:
            query = query.where(Empleado.estado == estado)

        total_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total = total_result.scalar_one()
        query = query.offset(skip).limit(limit).order_by(Empleado.fecha_ingreso.desc())
        result = await db.execute(query)
        items = result.scalars().all()
        return items, total

    async def get_with_usuario(self, db: AsyncSession, empleado_id: int) -> Optional[Empleado]:
        """Devuelve un `Empleado` cargando la relación `usuario` (selectinload), o None."""
        stmt = select(Empleado).where(Empleado.id == empleado_id).options(selectinload(Empleado.usuario))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

empleado = CRUDEmpleado(Empleado)