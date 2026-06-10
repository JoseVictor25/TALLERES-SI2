import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy import select
from app.models.taller import Taller

DATABASE_URL = "postgresql+asyncpg://postgres:cfF4EbfafdAfaBf5bBBf4GcgbF3EbA6b@zephyr.proxy.rlwy.net:39150/railway"
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test():
    async with AsyncSessionLocal() as db:
        stmt = select(Taller).options(
            selectinload(Taller.solicitud).selectinload("usuario_solicita").selectinload("persona")
        ).limit(1)
        result = await db.execute(stmt)
        taller = result.scalar_one_or_none()
        if taller:
            print("Taller:", taller.nombre)
            if taller.solicitud and taller.solicitud.usuario_solicita and taller.solicitud.usuario_solicita.persona:
                persona = taller.solicitud.usuario_solicita.persona
                print("Creador:", persona.nombre, persona.apellido_p)
                print("Email Creador:", persona.email)
            else:
                print("Sin info del creador")

asyncio.run(test())
