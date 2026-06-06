import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.rol import Rol
from sqlalchemy import select

ROLES = [
    {"nombre": "cliente", "descripcion": "Cliente / Conductor"},
    {"nombre": "Mecanico", "descripcion": "Técnico del taller"},
    {"nombre": "Administrador del Taller", "descripcion": "Dueño o Administrador de un Taller"},
    {"nombre": "Administrador del Sistema", "descripcion": "Administrador global de la plataforma"}
]

async def seed_roles():
    async with AsyncSessionLocal() as db:
        for rol_data in ROLES:
            result = await db.execute(select(Rol).where(Rol.nombre == rol_data["nombre"]))
            if not result.scalar_one_or_none():
                nuevo_rol = Rol(nombre=rol_data["nombre"])
                db.add(nuevo_rol)
                print(f"Rol creado: {rol_data['nombre']}")
        
        await db.commit()
        print("Roles verificados y creados exitosamente.")

if __name__ == "__main__":
    asyncio.run(seed_roles())
