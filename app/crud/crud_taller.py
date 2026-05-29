from app.crud.base import CRUDBase
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.taller import Taller, EstadoTaller
from sqlalchemy import select, func
from typing import Tuple, List, Optional
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol

class CRUDTaller(CRUDBase[Taller]):
    async def get_by_solicitud(self, db: AsyncSession, id_solicitud: int):
        result = await db.execute(select(Taller).where(Taller.id_solicitud_afiliacion == id_solicitud))
        return result.scalar_one_or_none()
    
    async def get_by_nombre(self, db: AsyncSession, nombre: str):
        result = await db.execute(select(Taller).where(Taller.nombre == nombre))
        return result.scalar_one_or_none()
    
    async def get_by_usuario_admin(
        self, db: AsyncSession, id_usuario: int, skip: int = 0, limit: int = 10
    ) -> Tuple[List[Taller], int]:
        """
        Obtiene los talleres donde el usuario tiene rol admin_taller o super_admin_taller.
        Retorna lista paginada y total de registros.
        """
        # Subconsulta para obtener ids de talleres
        from app.core.constants import ROL_ADMIN_TALLER, ROL_SUPER_ADMIN_TALLER
        stmt = select(Taller).join(
            RolUsuario, Taller.id == RolUsuario.id_taller
        ).join(
            Rol, Rol.id == RolUsuario.id_rol
        ).where(
            RolUsuario.id_usuario == id_usuario,
            Rol.nombre.in_([ROL_ADMIN_TALLER, ROL_SUPER_ADMIN_TALLER])
        ).distinct()

        # Total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await db.execute(count_stmt)
        total = total.scalar_one()

        # Paginación
        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()
        return items, total

    async def get_paginated(self, db: AsyncSession, skip: int = 0, limit: int = 10, estado: Optional[EstadoTaller] = None) -> Tuple[List[Taller], int]:
        """
        Obtiene talleres paginados; si `estado` se provee, filtra por ese estado.
        """
        stmt = select(Taller)
        if estado is not None:
            stmt = stmt.where(Taller.estado == estado)

        total_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
        total = total_result.scalar_one()

        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()
        return items, total

taller = CRUDTaller(Taller)