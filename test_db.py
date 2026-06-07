import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

async def main():
    engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost/taller_db')
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        res = await session.execute(text('SELECT ST_X(s.ubicacion::geometry), ST_Y(s.ubicacion::geometry), ST_X(t.ubicacion::geometry), ST_Y(t.ubicacion::geometry), ss.distancia_km FROM solicitud_servicio ss JOIN solicitud_diagnostico s ON ss.id_diagnostico = s.id JOIN taller t ON ss.id_taller = t.id ORDER BY ss.id DESC LIMIT 5;'))
        # ALTER TYPE no puede correr en un bloque de transaccion
        await session.execute(text("COMMIT"))
        await session.execute(text("ALTER TYPE estadosolicitudservicio ADD VALUE IF NOT EXISTS 'cotizacion_rechazada'"))
        print("Enum updated!")
    await engine.dispose()

asyncio.run(main())
