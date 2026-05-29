import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.vehiculo_taller import VehiculoTaller

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(VehiculoTaller).where(VehiculoTaller.id_taller == 1))
        vehiculos = result.scalars().all()
        if not vehiculos:
            print("No hay vehiculos_taller para el taller 1")
        else:
            for v in vehiculos:
                print(f"ID: {v.id}, Matricula: {v.matricula}, Modelo: {v.modelo}, Estado: {v.estado}")

if __name__ == "__main__":
    asyncio.run(main())
