from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.config import settings
from app.core.deps import get_current_usuario
from app.models.usuario import Usuario
from app.models.tenant import Tenant
import stripe

router = APIRouter(prefix="/tenants", tags=["SaaS Tenants"])

stripe.api_key = settings.STRIPE_SECRET_KEY

@router.post("/subscribe")
async def subscribe(
    plan: str = Query("basico", description="El plan elegido"),
    taller_name: str = Query(None, description="El nombre del taller"),
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint temporal para iniciar la suscripción y devolver una URL de Checkout
    """
    usuario = current_usuario
    if not usuario:
        raise HTTPException(status_code=400, detail="Usuario no encontrado")

    try:
        # Aquí en producción se conectaría a Stripe para generar la sesión
        # y se enviaría el metadata={'usuario_id': usuario.id, 'taller_name': taller_name}
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': 'Suscripción Plataforma Inteligente de Talleres',
                        },
                        'unit_amount': 2999, # $29.99
                        'recurring': {'interval': 'month'}
                    },
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f"{settings.FRONTEND_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/payment-cancel",
            metadata={
                "id_usuario_creador": current_usuario.id
            }
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Recibe el evento de Stripe cuando un pago es exitoso para crear el Tenant.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Si el pago de la suscripción fue exitoso
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Recuperar el ID del usuario que compró la suscripción
        id_usuario = session.get("metadata", {}).get("id_usuario_creador")
        taller_name = session.get("metadata", {}).get("taller_name")
        
        if id_usuario:
            # Crear un nuevo Tenant para este cliente
            nombre_taller = taller_name if taller_name else f"Red de Talleres {id_usuario}"
            nuevo_tenant = Tenant(
                nombre=nombre_taller, # Nombre genérico si no lo envían
                codigo_acceso=f"ORG-{id_usuario}",
                stripe_customer_id=session.get("customer"),
                stripe_subscription_id=session.get("subscription")
            )
            db.add(nuevo_tenant)
            await db.commit()
            await db.refresh(nuevo_tenant)
            
            # Actualizar al usuario para que sea el dueño de este Tenant
            from app.crud.crud_usuario import usuario as crud_usuario
            usuario = await crud_usuario.get(db, int(id_usuario))
            if usuario:
                usuario.tenant_id = nuevo_tenant.id
                
                # Asignar rol de Administrador del Taller si no lo tiene
                from app.models.rol import Rol
                from app.models.rol_usuario import RolUsuario
                from sqlalchemy import select
                
                # Buscar el rol
                result = await db.execute(select(Rol).where(Rol.nombre == "Administrador del Taller"))
                rol_admin_taller = result.scalar_one_or_none()
                
                if not rol_admin_taller:
                    rol_admin_taller = Rol(nombre="Administrador del Taller", descripcion="Rol admin taller")
                    db.add(rol_admin_taller)
                    await db.commit()
                    await db.refresh(rol_admin_taller)
                
                # CREAR SOLICITUD Y TALLER AUTOMÁTICAMENTE
                from app.models.solicitud_afiliacion import SolicitudAfiliacion, EstadoSolicitudAfiliacion
                from app.models.taller import Taller, EstadoTaller
                
                # 1. Crear Solicitud Aprobada
                nueva_soli = SolicitudAfiliacion(
                    nombre=nombre_taller,
                    ubicacion='POINT(-63.18117 -17.78629)', # Ubicación por defecto (ej. Santa Cruz)
                    telefono="00000000",
                    email="admin@taller.com",
                    estado=EstadoSolicitudAfiliacion.aprobada,
                    id_usuario_solicita=usuario.id
                )
                db.add(nueva_soli)
                await db.flush()
                
                # 2. Crear Taller
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

                # 3. Verificar si ya lo tiene (con id_taller)
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

    return {"status": "success"}

@router.post("/simulate-webhook")
async def simulate_stripe_webhook(
    id_usuario: int,
    taller_name: str = Query(None, description="El nombre del taller provisto"),
    db: AsyncSession = Depends(get_db)
):
    """
    ENDPOINT DE PRUEBA LOCAL: Simula que Stripe confirmó el pago.
    No usar en producción.
    """
    nuevo_tenant = Tenant(
        nombre=taller_name if taller_name else f"Red de Talleres {id_usuario}",
        codigo_acceso=f"ORG-{id_usuario}",
        stripe_customer_id="cus_test_123",
        stripe_subscription_id="sub_test_123"
    )
    db.add(nuevo_tenant)
    await db.commit()
    await db.refresh(nuevo_tenant)
    
    from app.crud.crud_usuario import usuario as crud_usuario
    usuario = await crud_usuario.get(db, id_usuario)
    if usuario:
        usuario.tenant_id = nuevo_tenant.id
        
        # Asignar rol de Administrador del Taller
        from app.models.rol import Rol
        from app.models.rol_usuario import RolUsuario
        from sqlalchemy import select
        
        result = await db.execute(select(Rol).where(Rol.nombre == "Administrador del Taller"))
        rol_admin_taller = result.scalar_one_or_none()
        
        if rol_admin_taller:
            # CREAR SOLICITUD Y TALLER AUTOMÁTICAMENTE ANTES DEL ROL
            from app.models.solicitud_afiliacion import SolicitudAfiliacion, EstadoSolicitudAfiliacion
            from app.models.taller import Taller, EstadoTaller
            
            nombre_taller = taller_name if taller_name else f"Red de Talleres {id_usuario}"

            # 1. Crear Solicitud Aprobada
            nueva_soli = SolicitudAfiliacion(
                nombre=nombre_taller,
                ubicacion='POINT(-63.18117 -17.78629)', # Ubicación por defecto (ej. Santa Cruz)
                telefono="00000000",
                email="admin@taller.com",
                estado=EstadoSolicitudAfiliacion.aprobada,
                id_usuario_solicita=usuario.id
            )
            db.add(nueva_soli)
            await db.flush()
            
            # 2. Crear Taller
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

            # 3. Asignar rol
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

    return {"status": "success", "tenant_id": nuevo_tenant.id}
