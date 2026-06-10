import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.db.session import engine, AsyncSessionLocal
from app.models.taller import Taller
from app.models.solicitud_servicio import SolicitudServicio
from app.models.diagnostico import Diagnostico
from app.models.incidente import Incidente

async def main():
    async with AsyncSessionLocal() as db:
        # Get first taller
        result = await db.execute(select(Taller).limit(1))
        taller = result.scalar_one_or_none()
        if not taller:
            print("No taller found")
            return
            
        print(f"Taller: {taller.id} - {taller.nombre}")
        
        # Check incidentes por tipo
        query_tipos = (
            select(Incidente.id, Diagnostico.id, SolicitudServicio.id)
            .select_from(Incidente)
            .join(Diagnostico, Diagnostico.id == Incidente.id_diagnostico)
            .join(SolicitudServicio, SolicitudServicio.id_diagnostico == Diagnostico.id)
            .where(SolicitudServicio.id_taller == taller.id)
        )
        result_tipos = await db.execute(query_tipos)
        print("Incidentes:", result_tipos.all())

        # Check ubicacion
        query_ubicacion = select(SolicitudServicio.ubicacion).where(SolicitudServicio.id_taller == taller.id)
        result_ubi = await db.execute(query_ubicacion)
        print("Ubicaciones:", result_ubi.all())

if __name__ == "__main__":
    asyncio.run(main())
