import asyncio
from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.taller import Taller
from app.models.usuario import Usuario

async def main():
    async with async_session_maker() as db:
        res = await db.execute(select(Taller))
        print("Talleres:")
        print([(t.id, t.nombre) for t in res.scalars().all()])
        
        res = await db.execute(select(Usuario.email, Usuario.tenant_id, Usuario.id))
        print("Usuarios:")
        print(res.all())

asyncio.run(main())
