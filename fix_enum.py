import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    db_url = os.getenv("DATABASE_URL")
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute("ALTER TYPE estadosolicitudservicio ADD VALUE IF NOT EXISTS 'cotizacion_rechazada'")
        await conn.execute("ALTER TYPE estadosolicitudservicio ADD VALUE IF NOT EXISTS 'cancelada'")
        await conn.execute("ALTER TYPE estadosolicitudservicio ADD VALUE IF NOT EXISTS 'expirada'")
        print("Enums updated successfully")
    except Exception as e:
        print("Error:", e)
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
