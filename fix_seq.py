import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def fix():
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT setval('especialidad_id_seq', (SELECT MAX(id) FROM especialidad));"))
        await db.commit()
        print("Secuencia de especialidad corregida.")

if __name__ == "__main__":
    asyncio.run(fix())
