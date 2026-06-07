import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.servicio_service import obtener_solicitudes_recientes
from dotenv import load_dotenv
import os

load_dotenv()
async def main():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as db:
        solicitudes = await obtener_solicitudes_recientes(db, id_taller=2, minutos=60)
        print("Solicitudes Recientes:")
        for s in solicitudes:
            print(s.id, s.estado, s.fecha)

asyncio.run(main())
