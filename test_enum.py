import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

async def main():
    engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost:5432/taller_db')
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as db:
        res = await db.execute(text("SELECT id FROM solicitud_servicio WHERE estado = 'cotizada' LIMIT 1"))
        row = res.fetchone()
        if not row:
            print('No hay solicitudes cotizadas')
            return
        id_sol = row[0]
        try:
            await db.execute(text(f"UPDATE solicitud_servicio SET estado = 'cotizacion_rechazada' WHERE id = {id_sol}"))
            await db.commit()
            print('Exito DB update')
        except Exception as e:
            print('DB Update error:', e)

asyncio.run(main())
