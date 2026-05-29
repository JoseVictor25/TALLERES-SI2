import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.bitacora_acceso import BitacoraAcceso

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(BitacoraAcceso))
        items = res.scalars().all()
        print(f"Found {len(items)} items")

asyncio.run(main())
