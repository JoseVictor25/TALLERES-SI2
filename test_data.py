import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import cast
from geoalchemy2.types import Geometry

from app.db.session import AsyncSessionLocal
from app.models.taller import Taller
from app.models.solicitud_servicio import SolicitudServicio
from app.models.diagnostico import Diagnostico
from app.models.incidente import Incidente
from app.models.tipo_incidente import TipoIncidente
from app.models.solicitud_diagnostico import SolicitudDiagnostico

async def main():
    async with AsyncSessionLocal() as db:
        # Loop all talleres
        result = await db.execute(select(Taller))
        talleres = result.scalars().all()
        
        for taller in talleres:
            print(f"\n--- Taller: {taller.id} - {taller.nombre} ---")
            
            # Count total SolicitudServicio for taller
            count_sol = await db.scalar(select(func.count(SolicitudServicio.id)).where(SolicitudServicio.id_taller == taller.id))
            print("Total SolicitudServicio para taller:", count_sol)
            
            # See if they have ubicacion
            count_ubi = await db.scalar(select(func.count(SolicitudServicio.id)).where(SolicitudServicio.id_taller == taller.id, SolicitudServicio.ubicacion != None))
            print("SolicitudServicio con ubicacion:", count_ubi)

            # Let's check the location from SolicitudDiagnostico
            query_sd_ubi = (
                select(func.count(SolicitudDiagnostico.id))
                .join(Diagnostico, Diagnostico.id_solicitud_diagnostico == SolicitudDiagnostico.id)
                .join(SolicitudServicio, SolicitudServicio.id_diagnostico == Diagnostico.id)
                .where(SolicitudServicio.id_taller == taller.id, SolicitudDiagnostico.ubicacion != None)
            )
            count_sd_ubi = await db.scalar(query_sd_ubi)
            print("SolicitudDiagnostico (relacionadas al servicio) con ubicacion:", count_sd_ubi)
            
            # Count Incidentes for taller
            query_inc = (
                select(func.count(Incidente.id_diagnostico))
                .join(Diagnostico, Diagnostico.id == Incidente.id_diagnostico)
                .join(SolicitudServicio, SolicitudServicio.id_diagnostico == Diagnostico.id)
                .where(SolicitudServicio.id_taller == taller.id)
            )
            count_inc = await db.scalar(query_inc)
            print("Total Incidentes para taller:", count_inc)

if __name__ == "__main__":
    asyncio.run(main())
