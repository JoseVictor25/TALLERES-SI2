import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.usuario import Usuario
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol
from sqlalchemy.orm import selectinload

async def check_roles():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Usuario).options(selectinload(Usuario.roles)).where(Usuario.id == 4))
        usuario = result.scalar_one_or_none()
        
        if usuario:
            print(f"Usuario {usuario.nombre} (ID: {usuario.id}, Tenant ID: {usuario.tenant_id})")
            for ru in usuario.roles:
                result_rol = await db.execute(select(Rol).where(Rol.id == ru.id_rol))
                rol = result_rol.scalar_one_or_none()
                rol_nombre = rol.nombre if rol else "Unknown"
                print(f"  - Rol: {rol_nombre} (Taller ID: {ru.id_taller})")
                
        # Asegurarnos de que tenga el rol si no lo tiene y tiene tenant
        if usuario and usuario.tenant_id:
            has_admin = False
            for ru in usuario.roles:
                result_rol = await db.execute(select(Rol).where(Rol.id == ru.id_rol))
                rol = result_rol.scalar_one_or_none()
                if rol and rol.nombre == "Administrador del Taller":
                    has_admin = True
                    
            if not has_admin:
                print("El usuario no tiene el rol. Asignándolo ahora...")
                # Buscar o crear rol
                result_rol = await db.execute(select(Rol).where(Rol.nombre == "Administrador del Taller"))
                rol_admin = result_rol.scalar_one_or_none()
                if not rol_admin:
                    rol_admin = Rol(nombre="Administrador del Taller", descripcion="Admin")
                    db.add(rol_admin)
                    await db.commit()
                    await db.refresh(rol_admin)
                
                # Para Taller, buscaremos si hay alguno con este tenant
                from app.models.taller import Taller
                result_taller = await db.execute(select(Taller).where(Taller.tenant_id == usuario.tenant_id))
                taller = result_taller.scalar_one_or_none()
                
                if taller:
                    nuevo_rol = RolUsuario(id_usuario=usuario.id, id_rol=rol_admin.id, id_taller=taller.id)
                    db.add(nuevo_rol)
                    await db.commit()
                    print("Rol asignado correctamente.")
                else:
                    print("ERROR: No se encontró un taller para el tenant del usuario.")
            else:
                print("El usuario ya tiene el rol en la base de datos.")

if __name__ == "__main__":
    asyncio.run(check_roles())
