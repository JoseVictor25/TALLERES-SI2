import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from app.models.taller import Taller
from app.models.servicio import Servicio, EstadoServicio
from app.models.solicitud_servicio import SolicitudServicio
from app.models.metrica import Metrica
from app.models.incidente import Incidente
from app.models.tipo_incidente import TipoIncidente
from app.models.diagnostico import Diagnostico
from geoalchemy2.functions import ST_X, ST_Y
import os

DATABASE_URL = "postgresql+asyncpg://postgres:cfF4EbfafdAfaBf5bBBf4GcgbF3EbA6b@zephyr.proxy.rlwy.net:39150/railway"
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test():
    async with AsyncSessionLocal() as db:
        taller_id = 1
        current_tenant = 1
        print("1")
        query_asignacion = select(func.avg(Metrica.tiempo_respuesta)).join(Servicio).where(Servicio.id_taller == taller_id)
        avg_asignacion = await db.scalar(query_asignacion)
        print("2")
        query_llegada = select(func.avg(Metrica.tiempo_llegada)).join(Servicio).where(Servicio.id_taller == taller_id)
        avg_llegada = await db.scalar(query_llegada)
        print("3")
        query_tipos = (
            select(TipoIncidente.concepto, func.count(Incidente.id_tipo_incidente))
            .join(Incidente.tipo_incidente)
            .join(Diagnostico, Diagnostico.id == Incidente.id_diagnostico)
            .join(SolicitudServicio, SolicitudServicio.id_diagnostico == Diagnostico.id)
            .where(SolicitudServicio.id_taller == taller_id)
            .group_by(TipoIncidente.concepto)
        )
        await db.execute(query_tipos)
        print("4")
        from sqlalchemy import cast
        from geoalchemy2.types import Geometry
        query_zonas = select(
            ST_Y(cast(SolicitudServicio.ubicacion, Geometry)).label('lat'),
            ST_X(cast(SolicitudServicio.ubicacion, Geometry)).label('lng')
        ).where(SolicitudServicio.id_taller == taller_id, SolicitudServicio.ubicacion != None)
        await db.execute(query_zonas)
        print("5")
        query_cancelados = select(func.count(Servicio.id)).where(Servicio.id_taller == taller_id, Servicio.estado == EstadoServicio.cancelado)
        await db.scalar(query_cancelados)
        print("6")
        query_sla_cumplidos = select(func.count(Metrica.id)).join(Servicio).where(
            Servicio.id_taller == taller_id,
            func.extract('epoch', Metrica.tiempo_llegada) <= 1800
        )
        await db.scalar(query_sla_cumplidos)
        print("7")
        query_ranking = (
            select(Taller.id, Taller.nombre, func.avg(Metrica.tiempo_resolucion).label("avg_resolucion"))
            .join(Servicio, Servicio.id_taller == Taller.id)
            .join(Metrica, Metrica.id_servicio == Servicio.id)
            .where(Taller.tenant_id == current_tenant)
            .group_by(Taller.id)
            .order_by(func.avg(Metrica.tiempo_resolucion).asc())
        )
        await db.execute(query_ranking)
        print("Done")

asyncio.run(test())
