from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.crud.base import CRUDBase
from app.models.solicitud_diagnostico import SolicitudDiagnostico
from app.models.diagnostico import Diagnostico
from app.models.incidente import Incidente


class CRUDSolicitudDiagnostico(CRUDBase[SolicitudDiagnostico]):
    async def get(self, db: AsyncSession, id: int) -> Optional[SolicitudDiagnostico]:
        """Override get to eagerly load relationships"""
        result = await db.execute(
            select(SolicitudDiagnostico)
            .options(
                selectinload(SolicitudDiagnostico.evidencias),
                selectinload(SolicitudDiagnostico.diagnostico).selectinload(Diagnostico.incidentes).selectinload(Incidente.tipo_incidente),
                selectinload(SolicitudDiagnostico.diagnostico).selectinload(Diagnostico.solicitudes_servicio)
            )
            .where(SolicitudDiagnostico.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_persona_paginated(self, db: AsyncSession, id_persona: int, skip: int = 0, limit: int = 10) -> Tuple[List[SolicitudDiagnostico], int]:
        total_result = await db.execute(select(func.count()).select_from(SolicitudDiagnostico).where(SolicitudDiagnostico.id_persona == id_persona))
        total = total_result.scalar_one()
        result = await db.execute(
            select(SolicitudDiagnostico)
            .options(
                selectinload(SolicitudDiagnostico.evidencias),
                selectinload(SolicitudDiagnostico.diagnostico).selectinload(Diagnostico.incidentes).selectinload(Incidente.tipo_incidente),
                selectinload(SolicitudDiagnostico.diagnostico).selectinload(Diagnostico.solicitudes_servicio)
            )
            .where(SolicitudDiagnostico.id_persona == id_persona)
            .order_by(SolicitudDiagnostico.fecha.desc())
            .offset(skip)
            .limit(limit)
        )
        items = result.scalars().all()
        return items, total

    async def update_estado(self, db: AsyncSession, solicitud_id: int, estado) -> SolicitudDiagnostico:
        obj = await self.get(db, solicitud_id)
        if not obj:
            return None
        obj.estado = estado
        await db.flush()
        await db.refresh(obj)
        return obj


solicitud_diagnostico = CRUDSolicitudDiagnostico(SolicitudDiagnostico)
