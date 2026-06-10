import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.solicitud_servicio import SolicitudServicio

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SolicitudServicio.id, SolicitudServicio.fecha).order_by(SolicitudServicio.id.desc()).limit(5))
        solicitudes = result.all()
        for s in solicitudes:
            print(f"ID: {s.id}, Fecha: {s.fecha}, tzinfo: {s.fecha.tzinfo if s.fecha else 'None'}")

if __name__ == "__main__":
    asyncio.run(main())
