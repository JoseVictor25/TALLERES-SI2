"""
Endpoints para técnicos móvil - Gestión de servicios asignados
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.deps import get_current_usuario
from app.models.usuario import Usuario
from app.core.constants import ROL_TECNICO
from app.models.empleado import Empleado, EstadoEmpleado
from app.models.servicio import Servicio, EstadoServicio
from app.models.servicio_tecnico import ServicioTecnico
from app.models.servicio_vehiculo import ServicioVehiculo
from app.models.solicitud_servicio import SolicitudServicio
from app.models.diagnostico import Diagnostico
from app.models.taller import Taller
from app.models.vehiculo_taller import VehiculoTaller
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol
from app.models.historial_estado_servicio import HistorialEstadoServicio
from app.models.metrica import Metrica
from app.models.ubicacion_tecnico import UbicacionTecnico
from app.crud import empleado as empleado_crud
from app.crud import crud_empleado_ubicacion
from geoalchemy2.shape import to_shape
from pydantic import BaseModel
from datetime import datetime
import math
from app.core.websocket_manager import manager as ws_manager

router = APIRouter(prefix="/tecnico", tags=["Técnico - Servicios Móvil"])


# ============================================================
# SCHEMAS
# ============================================================

class TallerTecnicoInfo(BaseModel):
    id: int
    nombre: str
    servicios_activos: int

class ClienteServicioInfo(BaseModel):
    nombre: str
    telefono: Optional[str]
    ubicacion_lat: float
    ubicacion_lon: float

class VehiculoAsignadoInfo(BaseModel):
    id_vehiculo_taller: int
    matricula: str
    marca: str
    modelo: str

class DiagnosticoInfo(BaseModel):
    id: int
    descripcion: Optional[str]
    nivel_confianza: float
    fecha: datetime

class ServicioTecnicoResponse(BaseModel):
    id: int
    numero: Optional[int] = None
    fecha: datetime
    estado: str
    estado_descripcion: str
    cliente: ClienteServicioInfo
    diagnostico: DiagnosticoInfo
    vehiculos_asignados: List[VehiculoAsignadoInfo]
    taller_nombre: str
    distancia_cliente_km: Optional[float]

class ActualizarEstadoRequest(BaseModel):
    nuevo_estado: str
    ubicacion_tecnico: Optional[str] = None  # JSON string con lat, lon, timestamp

class ActualizarUbicacionRequest(BaseModel):
    latitud: float
    longitud: float


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia entre dos puntos geográficos usando la fórmula de Haversine
    Retorna la distancia en kilómetros
    """
    R = 6371  # Radio de la Tierra en km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def get_estado_descripcion(estado: str) -> str:
    """Retorna la descripción en español del estado"""
    map_estados = {
        'creado': 'Creado',
        'tecnico_asignado': 'Técnico Asignado',
        'en_camino': 'En Camino',
        'en_lugar': 'En el Lugar',
        'en_atencion': 'En Atención',
        'finalizado': 'Finalizado',
        'cancelado': 'Cancelado'
    }
    return map_estados.get(estado, estado)


async def verificar_tecnico_en_taller(
    db: AsyncSession,
    usuario_id: int,
    taller_id: int
) -> Empleado:
    """
    Verifica que el usuario es técnico en el taller especificado
    Retorna el empleado si es válido, lanza excepción si no
    """
    # Verificar que el usuario tiene rol de técnico en el taller
    result = await db.execute(
        select(RolUsuario).join(Rol).where(
            and_(
                RolUsuario.id_usuario == usuario_id,
                RolUsuario.id_taller == taller_id,
                Rol.nombre == ROL_TECNICO
            )
        )
    )
    
    rol_usuario = result.scalar_one_or_none()
    if not rol_usuario:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos de técnico en este taller"
        )
    
    # Obtener el empleado
    empleado = await empleado_crud.get_active_by_usuario_taller(db, usuario_id, taller_id)
    if not empleado:
        raise HTTPException(
            status_code=404,
            detail="No se encontró registro de empleado activo en este taller"
        )
    
    return empleado


async def verificar_tecnico_asignado_servicio(
    db: AsyncSession,
    empleado_id: int,
    servicio_id: int
) -> bool:
    """
    Verifica que el técnico está asignado al servicio
    """
    result = await db.execute(
        select(ServicioTecnico).where(
            and_(
                ServicioTecnico.id_empleado == empleado_id,
                ServicioTecnico.id_servicio == servicio_id
            )
        )
    )
    
    return result.scalar_one_or_none() is not None


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/talleres", response_model=List[TallerTecnicoInfo])
async def obtener_talleres_tecnico(
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene la lista de talleres donde el técnico puede trabajar,
    con el contador de servicios activos en cada uno
    """
    # Obtener talleres donde el usuario tiene rol de técnico
    result = await db.execute(
        select(Taller, RolUsuario.id_taller)
        .join(RolUsuario, RolUsuario.id_taller == Taller.id)
        .join(Rol, Rol.id == RolUsuario.id_rol)
        .where(
            and_(
                RolUsuario.id_usuario == current_usuario.id,
                Rol.nombre == ROL_TECNICO
            )
        )
    )
    
    talleres_data = result.all()
    
    if not talleres_data:
        return []
    
    # Para cada taller, contar servicios activos donde el técnico está asignado
    talleres_info = []
    for taller, taller_id in talleres_data:
        # Obtener empleado del técnico en este taller
        empleado = await empleado_crud.get_active_by_usuario_taller(
            db, current_usuario.id, taller_id
        )
        
        if not empleado:
            continue
        
        # Contar servicios activos asignados al técnico
        count_result = await db.execute(
            select(func.count(Servicio.id))
            .join(ServicioTecnico, ServicioTecnico.id_servicio == Servicio.id)
            .where(
                and_(
                    ServicioTecnico.id_empleado == empleado.id,
                    Servicio.id_taller == taller_id,
                    Servicio.estado.in_([
                        EstadoServicio.tecnico_asignado,
                        EstadoServicio.en_camino,
                        EstadoServicio.en_lugar,
                        EstadoServicio.en_atencion
                    ])
                )
            )
        )
        
        servicios_activos = count_result.scalar_one()
        
        talleres_info.append(TallerTecnicoInfo(
            id=taller.id,
            nombre=taller.nombre,
            servicios_activos=servicios_activos
        ))
    
    return talleres_info


@router.get("/servicios/{taller_id}", response_model=List[ServicioTecnicoResponse])
async def obtener_servicios_asignados(
    taller_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene los servicios activos asignados al técnico en un taller específico
    """
    # Verificar que el usuario es técnico en el taller
    empleado = await verificar_tecnico_en_taller(db, current_usuario.id, taller_id)
    
    # Obtener servicios activos asignados al técnico
    result = await db.execute(
        select(Servicio)
        .join(ServicioTecnico, ServicioTecnico.id_servicio == Servicio.id)
        .where(
            and_(
                ServicioTecnico.id_empleado == empleado.id,
                Servicio.id_taller == taller_id,
                Servicio.estado.in_([
                    EstadoServicio.tecnico_asignado,
                    EstadoServicio.en_camino,
                    EstadoServicio.en_lugar,
                    EstadoServicio.en_atencion
                ])
            )
        )
        .order_by(Servicio.fecha.desc())
    )
    
    servicios = result.scalars().all()
    
    # Construir respuesta con información completa
    servicios_response = []
    for servicio in servicios:
        # Obtener taller
        taller = await db.get(Taller, servicio.id_taller)
        
        # Obtener solicitud y diagnóstico
        solicitud = await db.get(SolicitudServicio, servicio.id_solicitud_servicio)
        diagnostico = await db.get(Diagnostico, solicitud.id_diagnostico)
        
        # Obtener información del cliente
        from app.models.solicitud_diagnostico import SolicitudDiagnostico
        from app.models.persona import Persona
        
        solicitud_diag = await db.get(SolicitudDiagnostico, diagnostico.id_solicitud_diagnostico)
        persona = await db.get(Persona, solicitud_diag.id_persona)
        
        # Obtener ubicación del cliente
        ubicacion_cliente = None
        if solicitud.ubicacion:
            point = to_shape(solicitud.ubicacion)
            ubicacion_cliente = (point.y, point.x)  # lat, lon
        
        # Obtener vehículos asignados
        vehiculos_result = await db.execute(
            select(VehiculoTaller)
            .join(ServicioVehiculo, ServicioVehiculo.id_vehiculo_taller == VehiculoTaller.id)
            .where(ServicioVehiculo.id_servicio == servicio.id)
        )
        vehiculos = vehiculos_result.scalars().all()
        
        vehiculos_info = [
            VehiculoAsignadoInfo(
                id_vehiculo_taller=v.id,
                matricula=v.matricula,
                marca=v.marca,
                modelo=v.modelo
            )
            for v in vehiculos
        ]
        
        # Calcular distancia (si tenemos ubicación del cliente)
        distancia_km = None
        if ubicacion_cliente:
            # TODO: Aquí se podría obtener la ubicación actual del técnico
            # Por ahora retornamos None
            pass
        
        servicios_response.append(ServicioTecnicoResponse(
            id=servicio.id,
            numero=servicio.numero,
            fecha=servicio.fecha,
            estado=servicio.estado.value,
            estado_descripcion=get_estado_descripcion(servicio.estado.value),
            cliente=ClienteServicioInfo(
                nombre=persona.nombre or "Desconocido",
                telefono=persona.telefono,
                ubicacion_lat=ubicacion_cliente[0] if ubicacion_cliente else 0.0,
                ubicacion_lon=ubicacion_cliente[1] if ubicacion_cliente else 0.0
            ),
            diagnostico=DiagnosticoInfo(
                id=diagnostico.id,
                descripcion=diagnostico.descripcion,
                nivel_confianza=diagnostico.nivel_confianza,
                fecha=diagnostico.fecha
            ),
            vehiculos_asignados=vehiculos_info,
            taller_nombre=taller.nombre,
            distancia_cliente_km=distancia_km
        ))
    
    return servicios_response


@router.get("/servicios/{taller_id}/historial", response_model=List[ServicioTecnicoResponse])
async def obtener_historial_servicios_tecnico(
    taller_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el historial de servicios finalizados o cancelados
    donde el técnico fue asignado en un taller específico
    """
    # Verificar que el usuario es técnico en el taller
    empleado = await verificar_tecnico_en_taller(db, current_usuario.id, taller_id)
    
    # Obtener servicios históricos asignados al técnico
    result = await db.execute(
        select(Servicio)
        .join(ServicioTecnico, ServicioTecnico.id_servicio == Servicio.id)
        .where(
            and_(
                ServicioTecnico.id_empleado == empleado.id,
                Servicio.id_taller == taller_id,
                Servicio.estado.in_([
                    EstadoServicio.finalizado,
                    EstadoServicio.cancelado
                ])
            )
        )
        .order_by(Servicio.fecha.desc())
    )
    
    servicios = result.scalars().all()
    
    # Construir respuesta con información completa
    servicios_response = []
    for servicio in servicios:
        # Obtener taller
        taller = await db.get(Taller, servicio.id_taller)
        
        # Obtener solicitud y diagnóstico
        solicitud = await db.get(SolicitudServicio, servicio.id_solicitud_servicio)
        diagnostico = await db.get(Diagnostico, solicitud.id_diagnostico)
        
        # Obtener información del cliente
        from app.models.solicitud_diagnostico import SolicitudDiagnostico
        from app.models.persona import Persona
        
        solicitud_diag = await db.get(SolicitudDiagnostico, diagnostico.id_solicitud_diagnostico)
        persona = await db.get(Persona, solicitud_diag.id_persona)
        
        # Obtener ubicación del cliente
        ubicacion_cliente = None
        if solicitud.ubicacion:
            point = to_shape(solicitud.ubicacion)
            ubicacion_cliente = (point.y, point.x)  # lat, lon
        
        # Obtener vehículos asignados
        vehiculos_result = await db.execute(
            select(VehiculoTaller)
            .join(ServicioVehiculo, ServicioVehiculo.id_vehiculo_taller == VehiculoTaller.id)
            .where(ServicioVehiculo.id_servicio == servicio.id)
        )
        vehiculos = vehiculos_result.scalars().all()
        
        vehiculos_info = [
            VehiculoAsignadoInfo(
                id_vehiculo_taller=v.id,
                matricula=v.matricula,
                marca=v.marca,
                modelo=v.modelo
            )
            for v in vehiculos
        ]
        
        servicios_response.append(ServicioTecnicoResponse(
            id=servicio.id,
            numero=servicio.numero,
            fecha=servicio.fecha,
            estado=servicio.estado.value,
            estado_descripcion=get_estado_descripcion(servicio.estado.value),
            cliente=ClienteServicioInfo(
                nombre=persona.nombre or "Desconocido",
                telefono=persona.telefono,
                ubicacion_lat=ubicacion_cliente[0] if ubicacion_cliente else 0.0,
                ubicacion_lon=ubicacion_cliente[1] if ubicacion_cliente else 0.0
            ),
            diagnostico=DiagnosticoInfo(
                id=diagnostico.id,
                descripcion=diagnostico.descripcion,
                nivel_confianza=diagnostico.nivel_confianza,
                fecha=diagnostico.fecha
            ),
            vehiculos_asignados=vehiculos_info,
            taller_nombre=taller.nombre,
            distancia_cliente_km=None
        ))
    
    return servicios_response


@router.post("/servicios/{servicio_id}/actualizar-estado", status_code=status.HTTP_200_OK)
async def actualizar_estado_servicio(
    servicio_id: int,
    request: ActualizarEstadoRequest,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza el estado de un servicio asignado al técnico
    Valida las transiciones de estado permitidas
    """
    # Obtener el servicio
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    # Verificar que el usuario es técnico en el taller
    empleado = await verificar_tecnico_en_taller(db, current_usuario.id, servicio.id_taller)
    
    # Verificar que el técnico está asignado al servicio
    if not await verificar_tecnico_asignado_servicio(db, empleado.id, servicio_id):
        raise HTTPException(
            status_code=403,
            detail="No estás asignado a este servicio"
        )
    
    # Validar transición de estado
    estado_actual = servicio.estado.value
    nuevo_estado = request.nuevo_estado
    
    transiciones_validas = {
        'tecnico_asignado': ['en_camino', 'cancelado'],
        'en_camino': ['en_lugar', 'cancelado'],
        'en_lugar': ['en_atencion', 'cancelado'],
        'en_atencion': ['cancelado'] # finalizado is now handled by payment
    }
    
    if estado_actual not in transiciones_validas:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede cambiar el estado desde '{estado_actual}'"
        )
    
    if nuevo_estado not in transiciones_validas[estado_actual]:
        raise HTTPException(
            status_code=400,
            detail=f"Transición no válida de '{estado_actual}' a '{nuevo_estado}'"
        )
    
    # Actualizar estado
    try:
        from datetime import timezone
        ahora = datetime.now(timezone.utc)
        
        # 1. Obtener el historial previo para calcular el tiempo
        result = await db.execute(
            select(HistorialEstadoServicio)
            .where(HistorialEstadoServicio.id_servicio == servicio_id)
            .order_by(HistorialEstadoServicio.tiempo.desc())
            .limit(1)
        )
        ultimo_estado = result.scalar_one_or_none()
            
        # 2. Actualizar servicio
        servicio.estado = EstadoServicio(nuevo_estado)
        
        # 3. Registrar en Historial
        nuevo_historial = HistorialEstadoServicio(
            id_servicio=servicio_id,
            estado=EstadoServicio(nuevo_estado),
            tiempo=ahora
        )
        db.add(nuevo_historial)
        
        # 4. Actualizar Métricas según el estado alcanzado
        result_metrica = await db.execute(
            select(Metrica).where(Metrica.id_servicio == servicio_id)
        )
        metrica = result_metrica.scalar_one_or_none()
        if not metrica:
            metrica = Metrica(id_servicio=servicio_id)
            db.add(metrica)

        if nuevo_estado == 'en_camino':
            # tiempo_respuesta: desde creación del servicio hasta que el técnico sale
            # Buscamos el historial del estado tecnico_asignado para obtener la fecha real de asignación
            result_asig = await db.execute(
                select(HistorialEstadoServicio)
                .where(
                    HistorialEstadoServicio.id_servicio == servicio_id,
                    HistorialEstadoServicio.estado == EstadoServicio.tecnico_asignado
                )
                .order_by(HistorialEstadoServicio.tiempo.asc())
                .limit(1)
            )
            estado_asignado = result_asig.scalar_one_or_none()
            if estado_asignado:
                metrica.tiempo_respuesta = ahora - estado_asignado.tiempo
            else:
                # Fallback: usar fecha de creación del servicio
                if servicio.fecha:
                    fecha_creacion = servicio.fecha
                    if fecha_creacion.tzinfo is None:
                        from datetime import timezone as tz
                        fecha_creacion = fecha_creacion.replace(tzinfo=tz.utc)
                    metrica.tiempo_respuesta = ahora - fecha_creacion

        elif nuevo_estado == 'en_lugar':
            # tiempo_llegada: desde en_camino hasta en_lugar
            result_camino = await db.execute(
                select(HistorialEstadoServicio)
                .where(
                    HistorialEstadoServicio.id_servicio == servicio_id,
                    HistorialEstadoServicio.estado == EstadoServicio.en_camino
                )
                .order_by(HistorialEstadoServicio.tiempo.asc())
                .limit(1)
            )
            estado_en_camino = result_camino.scalar_one_or_none()
            if estado_en_camino:
                metrica.tiempo_llegada = ahora - estado_en_camino.tiempo

        elif nuevo_estado == 'finalizado':
            # tiempo_resolucion: desde en_lugar hasta finalizado
            result_lugar = await db.execute(
                select(HistorialEstadoServicio)
                .where(
                    HistorialEstadoServicio.id_servicio == servicio_id,
                    HistorialEstadoServicio.estado == EstadoServicio.en_lugar
                )
                .order_by(HistorialEstadoServicio.tiempo.asc())
                .limit(1)
            )
            estado_en_lugar = result_lugar.scalar_one_or_none()
            if estado_en_lugar:
                metrica.tiempo_resolucion = ahora - estado_en_lugar.tiempo
        
        await db.commit()
        await db.refresh(servicio)
        
        # Broadcast WS: notificar cambio de estado a clientes y admin taller
        broadcast_data = {
            "tipo": "estado_actualizado",
            "servicio_id": servicio.id,
            "estado": servicio.estado.value,
            "estado_descripcion": get_estado_descripcion(servicio.estado.value),
            "timestamp": ahora.isoformat()
        }
        await ws_manager.broadcast(f"servicio_{servicio_id}", broadcast_data)
        # También notificar al canal del taller
        await ws_manager.broadcast(f"taller_{servicio.id_taller}", broadcast_data)
        
        return {
            "message": "Estado actualizado exitosamente",
            "servicio_id": servicio.id,
            "nuevo_estado": servicio.estado.value,
            "estado_descripcion": get_estado_descripcion(servicio.estado.value)
        }
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Estado '{nuevo_estado}' no es válido"
        )


@router.post("/servicios/{servicio_id}/actualizar-ubicacion", status_code=status.HTTP_200_OK)
async def actualizar_ubicacion_tecnico(
    servicio_id: int,
    request: ActualizarUbicacionRequest,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza la ubicación GPS del técnico para seguimiento en tiempo real.
    Escribe en EmpleadoUbicacion para que el cliente pueda leerla.
    """
    # Obtener el servicio
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    # Verificar que el usuario es técnico en el taller
    empleado = await verificar_tecnico_en_taller(db, current_usuario.id, servicio.id_taller)
    
    # Verificar que el técnico está asignado al servicio
    if not await verificar_tecnico_asignado_servicio(db, empleado.id, servicio_id):
        raise HTTPException(
            status_code=403,
            detail="No estás asignado a este servicio"
        )
    
    # Validar que el servicio está en un estado activo
    if servicio.estado not in [
        EstadoServicio.tecnico_asignado,
        EstadoServicio.en_camino,
        EstadoServicio.en_lugar,
        EstadoServicio.en_atencion
    ]:
        raise HTTPException(
            status_code=400,
            detail="Solo se puede actualizar ubicación en servicios activos"
        )
    
    # Guardar ubicación usando EmpleadoUbicacion (tabla compartida con el cliente)
    # Esto desactiva la ubicación anterior y crea una nueva activa
    await crud_empleado_ubicacion.empleado_ubicacion.crear_ubicacion(
        db=db,
        id_empleado=empleado.id,
        latitud=request.latitud,
        longitud=request.longitud,
        id_servicio=servicio_id
    )
    await db.commit()
    
    return {
        "message": "Ubicación actualizada exitosamente",
        "servicio_id": servicio_id,
        "latitud": request.latitud,
        "longitud": request.longitud
    }
    # Nota: El tracking GPS en tiempo real ahora va por el canal WebSocket
    # ws/tracking/{servicio_id}. Este endpoint REST se mantiene como fallback.
