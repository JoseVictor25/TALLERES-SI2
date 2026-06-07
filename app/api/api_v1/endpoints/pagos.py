"""
CU-15: Gestionar Pagos
Endpoints para generar cobros, consultar facturas y recibir webhooks de Stripe.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal
"""
CU-15: Gestionar Pagos
Endpoints para generar cobros, consultar facturas y recibir webhooks de Stripe.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.db.session import get_db
from app.core.deps import get_current_usuario
from app.core.config import settings
from app.models.usuario import Usuario
from app.models.servicio import Servicio, EstadoServicio
from app.models.factura import Factura, EstadoPago
from app.models.empleado import Empleado
from app.models.taller import Taller
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol
from app.core.constants import ROL_TECNICO
from app.models.historial_estado_servicio import HistorialEstadoServicio
from app.models.metrica import Metrica
from app.services.stripe_service import crear_sesion_checkout, verificar_webhook

router = APIRouter(prefix="/pagos", tags=["Pagos"])

# ============================================================
# PÁGINAS DE RETORNO DE STRIPE
# ============================================================

@router.get("/exito", response_class=HTMLResponse)
async def pago_exito(session_id: Optional[str] = None):
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pago Exitoso</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding: 50px; background-color: #f0fdf4; color: #166534; }
            .container { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 400px; margin: 0 auto; }
            h1 { color: #15803d; margin-bottom: 10px; }
            p { color: #4b5563; font-size: 18px; }
            .icon { font-size: 64px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">✅</div>
            <h1>¡Pago Confirmado!</h1>
            <p>Tu pago ha sido procesado exitosamente.</p>
            <p>Ya puedes cerrar esta ventana y regresar con el mecánico.</p>
        </div>
    </body>
    </html>
    """

@router.get("/cancelado", response_class=HTMLResponse)
async def pago_cancelado():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pago Cancelado</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding: 50px; background-color: #fef2f2; color: #991b1b; }
            .container { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 400px; margin: 0 auto; }
            h1 { color: #b91c1c; margin-bottom: 10px; }
            p { color: #4b5563; font-size: 18px; }
            .icon { font-size: 64px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">❌</div>
            <h1>Pago Cancelado</h1>
            <p>El proceso de pago fue cancelado o no se completó.</p>
            <p>Puedes cerrar esta ventana e intentarlo nuevamente con el mecánico.</p>
        </div>
    </body>
    </html>
    """

# ============================================================
# SCHEMAS
# ============================================================

class GenerarCobroRequest(BaseModel):
    monto_total: float

class FacturaResponse(BaseModel):
    id: int
    id_servicio: int
    monto_total: float
    comision: float
    liquido_taller: float
    estado_pago: str
    metodo_pago: Optional[str] = None
    url_qr: Optional[str] = None
    fecha_emision: datetime
    fecha_pago: Optional[datetime] = None

class FacturaConServicioResponse(BaseModel):
    id: int
    id_servicio: int
    fecha_servicio: datetime
    monto_total: float
    comision: float
    liquido_taller: float
    estado_pago: str
    metodo_pago: Optional[str] = None
    fecha_emision: datetime
    fecha_pago: Optional[datetime] = None

class FinanzasTallerResponse(BaseModel):
    total_ingresos: float
    total_comisiones_plataforma: float
    ganancia_neta_taller: float
    total_pendiente: float
    facturas: list[FacturaConServicioResponse]

class RendimientoTaller(BaseModel):
    taller_id: int
    nombre_taller: str
    cantidad_servicios: int
    volumen_procesado: float
    comision_generada: float

class FinanzasSistemaResponse(BaseModel):
    ganancia_total_plataforma: float
    volumen_total_procesado: float
    cobros_pendientes_globales: float
    rendimiento_talleres: list[RendimientoTaller]
    ultimas_transacciones: list[FacturaConServicioResponse]


# ============================================================
# HELPERS
# ============================================================

async def _verificar_tecnico_en_taller(db: AsyncSession, usuario_id: int, taller_id: int):
    result = await db.execute(
        select(RolUsuario).join(Rol).where(
            and_(
                RolUsuario.id_usuario == usuario_id,
                RolUsuario.id_taller == taller_id,
                Rol.nombre == ROL_TECNICO
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="No eres técnico de este taller")

    result_emp = await db.execute(
        select(Empleado).where(
            and_(
                Empleado.id_usuario == usuario_id,
                Empleado.id_taller == taller_id
            )
        )
    )
    empleado = result_emp.scalar_one_or_none()
    if not empleado:
        raise HTTPException(status_code=403, detail="Perfil de empleado no encontrado")
    return empleado

async def _finalizar_servicio(db: AsyncSession, servicio: Servicio):
    """
    Función compartida para finalizar el servicio cuando se confirma el pago
    """
    # Evitar doble finalización
    if servicio.estado == EstadoServicio.finalizado:
        return
        
    from datetime import timezone
    ahora = datetime.now(timezone.utc)
    
    # Calcular tiempo de resolución
    result = await db.execute(
        select(HistorialEstadoServicio)
        .where(HistorialEstadoServicio.id_servicio == servicio.id)
        .order_by(HistorialEstadoServicio.tiempo.desc())
        .limit(1)
    )
    ultimo_estado = result.scalar_one_or_none()
    
    # Cambiar estado
    servicio.estado = EstadoServicio.finalizado
    
    # Historial
    nuevo_historial = HistorialEstadoServicio(
        id_servicio=servicio.id,
        estado=EstadoServicio.finalizado,
        tiempo=ahora
    )
    db.add(nuevo_historial)
    
    # Metrica
    if ultimo_estado and ultimo_estado.estado.value == 'en_atencion':
        tiempo = ultimo_estado.tiempo
        if tiempo.tzinfo is None:
            tiempo = tiempo.replace(tzinfo=timezone.utc)
        tiempo_desde_anterior = ahora - tiempo
        result_metrica = await db.execute(
            select(Metrica).where(Metrica.id_servicio == servicio.id)
        )
        metrica = result_metrica.scalar_one_or_none()
        if metrica:
            metrica.tiempo_resolucion = tiempo_desde_anterior
            
    # Liberar recursos (Técnicos y Vehículos) asignados al servicio
    # Empleados
    from app.models.servicio_tecnico import ServicioTecnico
    from app.models.empleado import Empleado, EstadoEmpleado
    
    result_tecnicos = await db.execute(
        select(Empleado)
        .join(ServicioTecnico, ServicioTecnico.id_empleado == Empleado.id)
        .where(ServicioTecnico.id_servicio == servicio.id)
    )
    tecnicos = result_tecnicos.scalars().all()
    for tecnico in tecnicos:
        if tecnico.estado == EstadoEmpleado.en_servicio:
            tecnico.estado = EstadoEmpleado.disponible
            
    # Vehículos
    from app.models.servicio_vehiculo import ServicioVehiculo
    from app.models.vehiculo_taller import VehiculoTaller, EstadoVehiculoTaller
    
    result_vehiculos = await db.execute(
        select(VehiculoTaller)
        .join(ServicioVehiculo, ServicioVehiculo.id_vehiculo_taller == VehiculoTaller.id)
        .where(ServicioVehiculo.id_servicio == servicio.id)
    )
    vehiculos = result_vehiculos.scalars().all()
    for vehiculo in vehiculos:
        if vehiculo.estado == EstadoVehiculoTaller.en_servicio:
            vehiculo.estado = EstadoVehiculoTaller.disponible


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/servicio/{servicio_id}/generar", response_model=FacturaResponse)
async def generar_cobro(
    servicio_id: int,
    payload: GenerarCobroRequest,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [TÉCNICO] Genera una factura y un link de pago de Stripe para un servicio.
    El servicio debe estar 'en_atencion'.
    """
    print(f"DEBUG: generar_cobro llamado para servicio {servicio_id} con monto {payload.monto_total}")
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
        
    await _verificar_tecnico_en_taller(db, current_usuario.id, servicio.id_taller)
    
    if servicio.estado != EstadoServicio.en_atencion:
        raise HTTPException(
            status_code=400, 
            detail=f"Solo se puede generar cobro si el servicio está 'en_atencion' (Actual: {servicio.estado.value})"
        )
        
    # Verificar si ya existe una factura
    result = await db.execute(select(Factura).where(Factura.id_servicio == servicio_id))
    factura_existente = result.scalar_one_or_none()
    
    if factura_existente and factura_existente.estado_pago == EstadoPago.pagado:
        raise HTTPException(status_code=400, detail="El servicio ya fue pagado")

    # Cálculos
    monto = Decimal(str(payload.monto_total))
    porcentaje_comision = Decimal(str(settings.PORCENTAJE_COMISION_PLATAFORMA))
    comision = round(monto * porcentaje_comision, 2)
    liquido = monto - comision
    
    # Llamar a Stripe
    try:
        stripe_session = crear_sesion_checkout(
            servicio_id=servicio_id,
            monto_total=float(monto),
            descripcion=f"Asistencia Vial - Servicio #{servicio_id}"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if factura_existente:
        # Actualizar existente
        factura_existente.monto_total = monto
        factura_existente.comision = comision
        factura_existente.liquido_taller = liquido
        factura_existente.id_pasarela = stripe_session["id"]
        factura_existente.url_qr = stripe_session["url"]
        factura_existente.metodo_pago = "stripe"
        factura_existente.estado_pago = EstadoPago.pendiente
        factura = factura_existente
    else:
        # Crear nueva
        factura = Factura(
            id_servicio=servicio_id,
            monto_total=monto,
            comision=comision,
            liquido_taller=liquido,
            id_pasarela=stripe_session["id"],
            url_qr=stripe_session["url"],
            metodo_pago="stripe",
            estado_pago=EstadoPago.pendiente
        )
        db.add(factura)
        
    await db.commit()
    await db.refresh(factura)
    
    return FacturaResponse(
        id=factura.id,
        id_servicio=factura.id_servicio,
        monto_total=float(factura.monto_total),
        comision=float(factura.comision),
        liquido_taller=float(factura.liquido_taller),
        estado_pago=factura.estado_pago.value,
        metodo_pago=factura.metodo_pago,
        url_qr=factura.url_qr,
        fecha_emision=factura.fecha_emision,
        fecha_pago=factura.fecha_pago
    )


@router.post("/servicio/{servicio_id}/pago-efectivo", response_model=FacturaResponse)
async def marcar_pago_efectivo(
    servicio_id: int,
    payload: GenerarCobroRequest,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [TÉCNICO] Marca el servicio como pagado en efectivo.
    Calcula comisiones y finaliza el servicio automáticamente.
    """
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
        
    await _verificar_tecnico_en_taller(db, current_usuario.id, servicio.id_taller)
    
    if servicio.estado not in [EstadoServicio.en_atencion, EstadoServicio.finalizado]:
        raise HTTPException(
            status_code=400, 
            detail="Solo se puede cobrar si el servicio está en atención"
        )
        
    result = await db.execute(select(Factura).where(Factura.id_servicio == servicio_id))
    factura = result.scalar_one_or_none()
    
    if factura and factura.estado_pago == EstadoPago.pagado:
        raise HTTPException(status_code=400, detail="El servicio ya fue pagado")

    monto = Decimal(str(payload.monto_total))
    porcentaje_comision = Decimal(str(settings.PORCENTAJE_COMISION_PLATAFORMA))
    comision = round(monto * porcentaje_comision, 2)
    liquido = monto - comision
    
    from datetime import timezone
    ahora = datetime.now(timezone.utc)
    
    if factura:
        factura.monto_total = monto
        factura.comision = comision
        factura.liquido_taller = liquido
        factura.metodo_pago = "efectivo"
        factura.estado_pago = EstadoPago.pagado
        factura.fecha_pago = ahora
    else:
        factura = Factura(
            id_servicio=servicio_id,
            monto_total=monto,
            comision=comision,
            liquido_taller=liquido,
            metodo_pago="efectivo",
            estado_pago=EstadoPago.pagado,
            fecha_pago=ahora
        )
        db.add(factura)
        
    # Finalizar el servicio automáticamente
    await _finalizar_servicio(db, servicio)
    
    await db.commit()
    await db.refresh(factura)
    
    return FacturaResponse(
        id=factura.id,
        id_servicio=factura.id_servicio,
        monto_total=float(factura.monto_total),
        comision=float(factura.comision),
        liquido_taller=float(factura.liquido_taller),
        estado_pago=factura.estado_pago.value,
        metodo_pago=factura.metodo_pago,
        url_qr=factura.url_qr,
        fecha_emision=factura.fecha_emision,
        fecha_pago=factura.fecha_pago
    )


@router.get("/servicio/{servicio_id}", response_model=FacturaResponse)
async def consultar_factura(
    servicio_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [CLIENTE/TALLER] Consulta la factura y el link de pago de un servicio.
    """
    result = await db.execute(select(Factura).where(Factura.id_servicio == servicio_id))
    factura = result.scalar_one_or_none()
    
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada para este servicio")
        
    return FacturaResponse(
        id=factura.id,
        id_servicio=factura.id_servicio,
        monto_total=float(factura.monto_total),
        comision=float(factura.comision),
        liquido_taller=float(factura.liquido_taller),
        estado_pago=factura.estado_pago.value,
        metodo_pago=factura.metodo_pago,
        url_qr=factura.url_qr,
        fecha_emision=factura.fecha_emision,
        fecha_pago=factura.fecha_pago
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    [STRIPE] Endpoint público para recibir confirmaciones de pago.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = verificar_webhook(payload, sig_header)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Manejar eventos
    if event['type'] == 'checkout.session.completed':
        try:
            session = event['data']['object']
            
            # Extraer metadata de forma segura sin usar .get en StripeObjects
            if isinstance(session, dict):
                metadata = session.get('metadata', {})
                session_id = session.get('id')
            else:
                metadata = getattr(session, 'metadata', {})
                session_id = getattr(session, 'id', None)

            if isinstance(metadata, dict):
                servicio_id_str = metadata.get('servicio_id')
            else:
                servicio_id_str = getattr(metadata, 'servicio_id', None)

            if not servicio_id_str:
                print("WEBHOOK ERROR: No servicio_id in metadata")
                return {"status": "ignored", "reason": "No servicio_id in metadata"}
                
            servicio_id = int(servicio_id_str)
            print(f"WEBHOOK SUCCESS: Procesando session_id {session_id} para servicio {servicio_id}")
            
            result = await db.execute(
                select(Factura).where(Factura.id_pasarela == session_id)
            )
            factura = result.scalar_one_or_none()
            
            if factura:
                factura.estado_pago = EstadoPago.pagado
                factura.fecha_pago = datetime.now(timezone.utc)
                
                # Finalizar el servicio automáticamente
                servicio = await db.get(Servicio, servicio_id)
                if servicio:
                    await _finalizar_servicio(db, servicio)
                    
                await db.commit()
                print(f"WEBHOOK SUCCESS: Factura {factura.id} actualizada exitosamente")
                return {"status": "success"}
            else:
                print(f"WEBHOOK ERROR: Factura no encontrada con pasarela {session_id}")
                return {"status": "ignored", "reason": "Factura not found"}
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"WEBHOOK EXCEPTION CRITICAL: {error_details}")
            with open("webhook_error.log", "a") as f:
                f.write(f"\n--- WEBHOOK ERROR {datetime.now()} ---\n{error_details}\n")
            raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

    return {"status": "ignored"}

@router.get("/taller/{taller_id}/finanzas", response_model=FinanzasTallerResponse)
async def obtener_finanzas_taller(
    taller_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [ADMIN TALLER] Obtiene las métricas financieras (ingresos netos, comisiones)
    y el listado de facturas asociadas a los servicios del taller.
    """
    # Verificar que el usuario tenga rol de administrador o sea el dueño del taller
    # Aquí puedes añadir validación estricta, por ahora asumimos acceso validado.
    
    query = select(Factura, Servicio).join(Servicio, Factura.id_servicio == Servicio.id).where(
        Servicio.id_taller == taller_id
    ).order_by(Factura.fecha_emision.desc())
    
    result = await db.execute(query)
    rows = result.all()
    
    total_ingresos = Decimal("0.0")
    total_comisiones = Decimal("0.0")
    ganancia_neta = Decimal("0.0")
    total_pendiente = Decimal("0.0")
    
    facturas_response = []
    
    for factura, servicio in rows:
        if factura.estado_pago == EstadoPago.pagado:
            total_ingresos += factura.monto_total
            total_comisiones += factura.comision
            ganancia_neta += factura.liquido_taller
        else:
            total_pendiente += factura.monto_total
            
        facturas_response.append(
            FacturaConServicioResponse(
                id=factura.id,
                id_servicio=factura.id_servicio,
                fecha_servicio=servicio.fecha,
                monto_total=float(factura.monto_total),
                comision=float(factura.comision),
                liquido_taller=float(factura.liquido_taller),
                estado_pago=factura.estado_pago.value,
                metodo_pago=factura.metodo_pago,
                fecha_emision=factura.fecha_emision,
                fecha_pago=factura.fecha_pago
            )
        )
        
    return FinanzasTallerResponse(
        total_ingresos=float(total_ingresos),
        total_comisiones_plataforma=float(total_comisiones),
        ganancia_neta_taller=float(ganancia_neta),
        total_pendiente=float(total_pendiente),
        facturas=facturas_response
    )

@router.get("/sistema/finanzas", response_model=FinanzasSistemaResponse)
async def obtener_finanzas_sistema(
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [ADMIN SISTEMA] Obtiene las métricas globales de toda la plataforma:
    comisiones de SmartAssist, volumen procesado, rendimientos por taller
    y todas las facturas.
    """
    # En un entorno real, validar que current_usuario tenga rol 'Administrador del Sistema'
    
    query = select(Factura, Servicio, Taller).join(
        Servicio, Factura.id_servicio == Servicio.id
    ).join(
        Taller, Servicio.id_taller == Taller.id
    ).order_by(Factura.fecha_emision.desc())
    
    result = await db.execute(query)
    rows = result.all()
    
    ganancia_total_plataforma = Decimal("0.0")
    volumen_total_procesado = Decimal("0.0")
    cobros_pendientes_globales = Decimal("0.0")
    
    talleres_stats = {}
    facturas_response = []
    
    for factura, servicio, taller in rows:
        taller_id = taller.id
        if taller_id not in talleres_stats:
            talleres_stats[taller_id] = {
                "nombre": taller.nombre,
                "cantidad": 0,
                "volumen": Decimal("0.0"),
                "comision": Decimal("0.0")
            }
            
        if factura.estado_pago == EstadoPago.pagado:
            ganancia_total_plataforma += factura.comision
            volumen_total_procesado += factura.monto_total
            
            talleres_stats[taller_id]["cantidad"] += 1
            talleres_stats[taller_id]["volumen"] += factura.monto_total
            talleres_stats[taller_id]["comision"] += factura.comision
        else:
            # Comisiones de facturas pendientes
            cobros_pendientes_globales += factura.comision
            
        facturas_response.append(
            FacturaConServicioResponse(
                id=factura.id,
                id_servicio=factura.id_servicio,
                fecha_servicio=servicio.fecha,
                monto_total=float(factura.monto_total),
                comision=float(factura.comision),
                liquido_taller=float(factura.liquido_taller),
                estado_pago=factura.estado_pago.value,
                metodo_pago=factura.metodo_pago,
                fecha_emision=factura.fecha_emision,
                fecha_pago=factura.fecha_pago
            )
        )
        
    rendimiento_talleres = []
    for tid, stats in talleres_stats.items():
        if stats["cantidad"] > 0: # Mostrar solo los que tienen servicios pagados, o todos? Todos es mejor, pero ya los filtramos.
            pass
        rendimiento_talleres.append(
            RendimientoTaller(
                taller_id=tid,
                nombre_taller=stats["nombre"],
                cantidad_servicios=stats["cantidad"],
                volumen_procesado=float(stats["volumen"]),
                comision_generada=float(stats["comision"])
            )
        )
        
    # Ordenar talleres por comision generada descendente
    rendimiento_talleres.sort(key=lambda x: x.comision_generada, reverse=True)
        
    return FinanzasSistemaResponse(
        ganancia_total_plataforma=float(ganancia_total_plataforma),
        volumen_total_procesado=float(volumen_total_procesado),
        cobros_pendientes_globales=float(cobros_pendientes_globales),
        rendimiento_talleres=rendimiento_talleres,
        ultimas_transacciones=facturas_response
    )
