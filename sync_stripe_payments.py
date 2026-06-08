import asyncio
import stripe
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.core.config import settings
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.models.rol import Rol
from app.models.rol_usuario import RolUsuario
from app.models.solicitud_afiliacion import SolicitudAfiliacion, EstadoSolicitudAfiliacion
from app.models.taller import Taller, EstadoTaller

stripe.api_key = settings.STRIPE_SECRET_KEY

async def sync_old_payments():
    print("Sincronizando pagos antiguos de Stripe...")
    
    # Obtener sesiones recientes de Stripe
    try:
        sessions = stripe.checkout.Session.list(limit=100)
    except Exception as e:
        print(f"Error al conectar con Stripe: {e}")
        return

    async with AsyncSessionLocal() as db:
        for session in sessions.data:
            if session.payment_status == 'paid':
                metadata = getattr(session, 'metadata', {})
                id_usuario_str = None
                taller_name = None
                
                if isinstance(metadata, dict):
                    id_usuario_str = metadata.get("id_usuario_creador")
                    taller_name = metadata.get("taller_name")
                else:
                    id_usuario_str = getattr(metadata, "id_usuario_creador", None)
                    taller_name = getattr(metadata, "taller_name", None)
                    
                stripe_subscription_id = getattr(session, "subscription", None)
                stripe_customer_id = getattr(session, "customer", None)
                
                if not id_usuario_str:
                    continue
                    
                id_usuario = int(id_usuario_str)
                
                # Verificar si ya tiene tenant creado
                if stripe_subscription_id:
                    result = await db.execute(select(Tenant).where(Tenant.stripe_subscription_id == stripe_subscription_id))
                    if result.scalar_one_or_none():
                        print(f"La sesión {session.id} ya fue procesada previamente.")
                        continue
                        
                print(f"Procesando sesión {session.id} para usuario {id_usuario}...")
                
                from app.crud.crud_usuario import usuario as crud_usuario
                usuario = await crud_usuario.get(db, id_usuario)
                
                if not usuario:
                    continue
                    
                if usuario.tenant_id is not None:
                    print(f"El usuario {id_usuario} ya tiene un tenant asociado. Omitiendo...")
                    continue
                
                nombre_taller = taller_name if taller_name else f"Red de Talleres {id_usuario}"
                nuevo_tenant = Tenant(
                    nombre=nombre_taller,
                    codigo_acceso=f"ORG-{id_usuario}",
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_subscription_id
                )
                db.add(nuevo_tenant)
                await db.commit()
                await db.refresh(nuevo_tenant)
                
                usuario.tenant_id = nuevo_tenant.id
                
                result = await db.execute(select(Rol).where(Rol.nombre == "Administrador del Taller"))
                rol_admin_taller = result.scalar_one_or_none()
                
                if not rol_admin_taller:
                    rol_admin_taller = Rol(nombre="Administrador del Taller", descripcion="Rol admin taller")
                    db.add(rol_admin_taller)
                    await db.commit()
                    await db.refresh(rol_admin_taller)
                
                nueva_soli = SolicitudAfiliacion(
                    nombre=nombre_taller,
                    ubicacion='POINT(-63.18117 -17.78629)',
                    telefono="00000000",
                    email="admin@taller.com",
                    estado=EstadoSolicitudAfiliacion.aprobada,
                    id_usuario_solicita=usuario.id
                )
                db.add(nueva_soli)
                await db.flush()
                
                nuevo_taller = Taller(
                    nombre=nombre_taller,
                    ubicacion='POINT(-63.18117 -17.78629)',
                    telefono="00000000",
                    email="admin@taller.com",
                    estado=EstadoTaller.activo,
                    id_solicitud_afiliacion=nueva_soli.id,
                    tenant_id=nuevo_tenant.id
                )
                db.add(nuevo_taller)
                await db.flush()
                
                result_ru = await db.execute(
                    select(RolUsuario).where(
                        RolUsuario.id_usuario == usuario.id,
                        RolUsuario.id_rol == rol_admin_taller.id,
                        RolUsuario.id_taller == nuevo_taller.id
                    )
                )
                if not result_ru.scalar_one_or_none():
                    nuevo_rol = RolUsuario(
                        id_usuario=usuario.id,
                        id_rol=rol_admin_taller.id,
                        id_taller=nuevo_taller.id
                    )
                    db.add(nuevo_rol)

                await db.commit()
                print(f"  -> Usuario {id_usuario} ({usuario.nombre}) ahora es Administrador del Taller.")

if __name__ == "__main__":
    asyncio.run(sync_old_payments())
