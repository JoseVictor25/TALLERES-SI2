import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy import select

from app.db.session import engine, async_session_maker
from app.models.usuario import Usuario
from app.models.rol import Rol
from app.models.rol_usuario import RolUsuario
from app.models.tenant import Tenant
from app.models.persona import Persona

async def main():
    async with async_session_maker() as db:
        query = (
            select(Usuario, Persona, Tenant)
            .join(Persona, Usuario.id_persona == Persona.id)
            .outerjoin(Tenant, Usuario.tenant_id == Tenant.id)
            .join(RolUsuario, RolUsuario.id_usuario == Usuario.id)
            .join(Rol, Rol.id == RolUsuario.id_rol)
            .where(Rol.nombre == "Administrador del Taller")
        )
        result = await db.execute(query)
        rows = result.unique().all()
        for usuario, persona, tenant in rows:
            print(f"Usuario: {usuario.nombre}, Persona: {persona.email}, Tenant: {tenant.nombre if tenant else 'None'}")
            if tenant:
                print(f"  Stripe Sub: {tenant.stripe_subscription_id}")

if __name__ == "__main__":
    asyncio.run(main())
