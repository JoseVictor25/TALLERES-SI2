"""
CU-13: Monitorear Servicio
Endpoints para que el cliente pueda seguir el estado de su servicio en tiempo real.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.core.deps import get_current_usuario
from app.models.usuario import Usuario
from app.models.servicio import Servicio, EstadoServicio
from app.models.servicio_tecnico import ServicioTecnico
from app.core.constants import ROL_ADMIN_TALLER
from app.models.servicio_vehiculo import ServicioVehiculo
from app.models.solicitud_servicio import SolicitudServicio
from app.models.solicitud_diagnostico import SolicitudDiagnostico
from app.models.diagnostico import Diagnostico
from app.models.taller import Taller
from app.models.empleado import Empleado
from app.models.vehiculo_taller import VehiculoTaller
from app.models.persona import Persona
from app.models.historial_estado_servicio import HistorialEstadoServicio
from app.models.metrica import Metrica
from app.models.ubicacion_tecnico import UbicacionTecnico
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol
from app.services.eta_service import calcular_eta
from geoalchemy2.shape import to_shape

router = APIRouter(prefix="/monitoreo", tags=["Monitoreo de Servicio"])


# ============================================================
# SCHEMAS DE RESPUESTA
# ============================================================

class TallerMonitoreoResponse(BaseModel):
    id: int
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None

class TecnicoMonitoreoResponse(BaseModel):
    id_empleado: int
    nombre: str

class VehiculoMonitoreoResponse(BaseModel):
    id: int
    matricula: str
    marca: str
    modelo: str

class DiagnosticoMonitoreoResponse(BaseModel):
    id: int
    descripcion: Optional[str] = None
    nivel_confianza: float

class HistorialEstadoResponse(BaseModel):
    estado: str
    estado_descripcion: str
    fecha: datetime
    tiempo_desde_anterior: Optional[float] = None  # segundos

class UbicacionTecnicoResponse(BaseModel):
    latitud: float
    longitud: float
    timestamp: datetime
    distancia_km: Optional[float] = None
    eta_minutos: Optional[float] = None
    metodo_eta: Optional[str] = None

class ServicioMonitoreoResponse(BaseModel):
    """Respuesta completa del monitoreo para el cliente móvil"""
    id: int
    fecha: datetime
    estado: str
    estado_descripcion: str

    # Datos del taller
    taller: TallerMonitoreoResponse

    # Técnicos asignados
    tecnicos: List[TecnicoMonitoreoResponse] = []

    # Vehículos del taller
    vehiculos: List[VehiculoMonitoreoResponse] = []

    # Diagnóstico
    diagnostico: Optional[DiagnosticoMonitoreoResponse] = None

    # Ubicación del cliente
    ubicacion_cliente_lat: Optional[float] = None
    ubicacion_cliente_lon: Optional[float] = None

    # Última ubicación conocida del técnico
    ubicacion_tecnico: Optional[UbicacionTecnicoResponse] = None

    # Timeline de eventos
    historial: List[HistorialEstadoResponse] = []

class ServicioListaClienteResponse(BaseModel):
    """Schema resumido para listar servicios del cliente"""
    id: int
    fecha: datetime
    estado: str
    estado_descripcion: str
    taller_nombre: str
    diagnostico_descripcion: Optional[str] = None


# ============================================================
# HELPERS
# ============================================================

ESTADO_DESCRIPCIONES = {
    "creado": "Servicio creado",
    "tecnico_asignado": "Técnico asignado",
    "en_camino": "Técnico en camino",
    "en_lugar": "Técnico en el lugar",
    "en_atencion": "En atención",
    "finalizado": "Servicio finalizado",
    "cancelado": "Servicio cancelado",
}

def get_descripcion_estado(estado: str) -> str:
    return ESTADO_DESCRIPCIONES.get(estado, estado)


async def _verificar_cliente_del_servicio(
    db: AsyncSession,
    servicio: Servicio,
    usuario_id: int
) -> bool:
    """
    Verifica que el usuario autenticado es el cliente que generó el servicio.
    Navega: Servicio → SolicitudServicio → Diagnostico → SolicitudDiagnostico → Persona → Usuario
    """
    if not servicio.id_solicitud_servicio:
        return False

    solicitud = await db.get(SolicitudServicio, servicio.id_solicitud_servicio)
    if not solicitud:
        return False

    diagnostico = await db.get(Diagnostico, solicitud.id_diagnostico)
    if not diagnostico:
        return False

    solicitud_diag = await db.get(SolicitudDiagnostico, diagnostico.id_solicitud_diagnostico)
    if not solicitud_diag:
        return False

    persona = await db.get(Persona, solicitud_diag.id_persona)
    if not persona:
        return False

    # Verificar que la persona del servicio corresponde al usuario autenticado
    result = await db.execute(
        select(Usuario).where(Usuario.id_persona == persona.id)
    )
    usuario_del_servicio = result.scalar_one_or_none()
    return usuario_del_servicio is not None and usuario_del_servicio.id == usuario_id


async def _es_admin_taller(db: AsyncSession, usuario_id: int, taller_id: int) -> bool:
    """Verifica si el usuario es administrador del taller"""
    result = await db.execute(
        select(RolUsuario).join(Rol).where(
            and_(
                RolUsuario.id_usuario == usuario_id,
                RolUsuario.id_taller == taller_id,
                Rol.nombre == ROL_ADMIN_TALLER
            )
        )
    )
    return result.scalar_one_or_none() is not None


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/mis-servicios", response_model=List[ServicioListaClienteResponse])
async def listar_mis_servicios(
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [CLIENTE] Lista todos los servicios del cliente autenticado (activos e históricos).
    Navega desde el usuario hasta los servicios a través de SolicitudDiagnostico → Diagnostico → SolicitudServicio → Servicio.
    """
    # Obtener persona del usuario
    persona = await db.get(Persona, current_usuario.id_persona)
    if not persona:
        raise HTTPException(status_code=404, detail="Perfil de persona no encontrado")

    # Obtener todas las solicitudes de diagnóstico del cliente
    result = await db.execute(
        select(SolicitudDiagnostico).where(SolicitudDiagnostico.id_persona == persona.id)
    )
    solicitudes_diag = result.scalars().all()

    servicios_response = []

    for sol_diag in solicitudes_diag:
        # Diagnósticos de esta solicitud
        result_diag = await db.execute(
            select(Diagnostico).where(Diagnostico.id_solicitud_diagnostico == sol_diag.id)
        )
        diagnosticos = result_diag.scalars().all()

        for diagnostico in diagnosticos:
            # Solicitudes de servicio de este diagnóstico
            result_ss = await db.execute(
                select(SolicitudServicio).where(SolicitudServicio.id_diagnostico == diagnostico.id)
            )
            solicitudes_servicio = result_ss.scalars().all()

            for sol_serv in solicitudes_servicio:
                # Servicio asociado
                result_serv = await db.execute(
                    select(Servicio).where(Servicio.id_solicitud_servicio == sol_serv.id)
                )
                servicio = result_serv.scalar_one_or_none()
                if not servicio:
                    continue

                taller = await db.get(Taller, servicio.id_taller)

                servicios_response.append(ServicioListaClienteResponse(
                    id=servicio.id,
                    fecha=servicio.fecha,
                    estado=servicio.estado.value,
                    estado_descripcion=get_descripcion_estado(servicio.estado.value),
                    taller_nombre=taller.nombre if taller else "Desconocido",
                    diagnostico_descripcion=diagnostico.descripcion
                ))

    # Ordenar por fecha descendente
    servicios_response.sort(key=lambda x: x.fecha, reverse=True)
    return servicios_response


@router.get("/servicio/{servicio_id}", response_model=ServicioMonitoreoResponse)
async def obtener_monitoreo_servicio(
    servicio_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [CLIENTE] Obtiene el estado completo de un servicio para monitoreo.
    Incluye: estado actual, datos del taller, técnicos, vehículos, diagnóstico,
    ubicación del cliente, última ubicación del técnico e historial de estados.
    """
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    # Verificar que el usuario es el cliente del servicio o admin del taller
    es_cliente = await _verificar_cliente_del_servicio(db, servicio, current_usuario.id)
    es_admin = await _es_admin_taller(db, current_usuario.id, servicio.id_taller)

    if not es_cliente and not es_admin:
        raise HTTPException(
            status_code=403,
            detail="No tienes acceso a este servicio"
        )

    # --- Taller ---
    taller = await db.get(Taller, servicio.id_taller)
    taller_response = TallerMonitoreoResponse(
        id=taller.id,
        nombre=taller.nombre,
        telefono=taller.telefono,
        email=taller.email,
        direccion=None  # taller no tiene direccion en el modelo actual
    )

    # --- Técnicos asignados ---
    result_tec = await db.execute(
        select(ServicioTecnico).where(ServicioTecnico.id_servicio == servicio_id)
    )
    asignaciones_tec = result_tec.scalars().all()

    tecnicos_response = []
    for asig in asignaciones_tec:
        empleado = await db.get(Empleado, asig.id_empleado)
        if empleado:
            usuario_tec = await db.get(Usuario, empleado.id_usuario)
            if usuario_tec:
                persona_tec = await db.get(Persona, usuario_tec.id_persona)
                tecnicos_response.append(TecnicoMonitoreoResponse(
                    id_empleado=empleado.id,
                    nombre=persona_tec.nombre if persona_tec else "Técnico"
                ))

    # --- Vehículos asignados ---
    result_veh = await db.execute(
        select(ServicioVehiculo).where(ServicioVehiculo.id_servicio == servicio_id)
    )
    asignaciones_veh = result_veh.scalars().all()

    vehiculos_response = []
    for asig in asignaciones_veh:
        veh = await db.get(VehiculoTaller, asig.id_vehiculo_taller)
        if veh:
            vehiculos_response.append(VehiculoMonitoreoResponse(
                id=veh.id,
                matricula=veh.matricula,
                marca=veh.marca,
                modelo=veh.modelo
            ))

    # --- Ubicación del cliente + Diagnóstico ---
    ubicacion_cliente_lat = None
    ubicacion_cliente_lon = None
    diagnostico_response = None

    if servicio.id_solicitud_servicio:
        solicitud = await db.get(SolicitudServicio, servicio.id_solicitud_servicio)
        if solicitud:
            if solicitud.ubicacion:
                point = to_shape(solicitud.ubicacion)
                ubicacion_cliente_lat = point.y
                ubicacion_cliente_lon = point.x

            diagnostico = await db.get(Diagnostico, solicitud.id_diagnostico)
            if diagnostico:
                diagnostico_response = DiagnosticoMonitoreoResponse(
                    id=diagnostico.id,
                    descripcion=diagnostico.descripcion,
                    nivel_confianza=float(diagnostico.nivel_confianza)
                )

    # --- Última ubicación del técnico ---
    ubicacion_tec_response = None
    result_ub = await db.execute(
        select(UbicacionTecnico)
        .where(UbicacionTecnico.id_servicio == servicio_id)
        .order_by(UbicacionTecnico.timestamp.desc())
        .limit(1)
    )
    ultima_ubicacion = result_ub.scalar_one_or_none()

    if ultima_ubicacion:
        lat_tec = float(ultima_ubicacion.latitud)
        lon_tec = float(ultima_ubicacion.longitud)

        eta_info = None
        if ubicacion_cliente_lat and ubicacion_cliente_lon:
            eta_info = calcular_eta(lat_tec, lon_tec, ubicacion_cliente_lat, ubicacion_cliente_lon)

        ubicacion_tec_response = UbicacionTecnicoResponse(
            latitud=lat_tec,
            longitud=lon_tec,
            timestamp=ultima_ubicacion.timestamp,
            distancia_km=eta_info["distancia_km"] if eta_info else None,
            eta_minutos=eta_info["eta_minutos"] if eta_info else None,
            metodo_eta=eta_info["metodo"] if eta_info else None
        )

    # --- Historial de estados ---
    result_hist = await db.execute(
        select(HistorialEstadosServicio)
        .where(HistorialEstadosServicio.id_servicio == servicio_id)
        .order_by(HistorialEstadosServicio.fecha.asc())
    )
    historial_db = result_hist.scalars().all()

    historial_response = [
        HistorialEstadoResponse(
            estado=h.estado.value,
            estado_descripcion=get_descripcion_estado(h.estado.value),
            fecha=h.fecha,
            tiempo_desde_anterior=float(h.tiempo_desde_anterior) if h.tiempo_desde_anterior else None
        )
        for h in historial_db
    ]

    return ServicioMonitoreoResponse(
        id=servicio.id,
        fecha=servicio.fecha,
        estado=servicio.estado.value,
        estado_descripcion=get_descripcion_estado(servicio.estado.value),
        taller=taller_response,
        tecnicos=tecnicos_response,
        vehiculos=vehiculos_response,
        diagnostico=diagnostico_response,
        ubicacion_cliente_lat=ubicacion_cliente_lat,
        ubicacion_cliente_lon=ubicacion_cliente_lon,
        ubicacion_tecnico=ubicacion_tec_response,
        historial=historial_response
    )


@router.get("/servicio/{servicio_id}/ubicacion-tecnico", response_model=UbicacionTecnicoResponse)
async def obtener_ubicacion_tecnico(
    servicio_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [CLIENTE] Obtiene la última ubicación GPS del técnico para el servicio indicado.
    Devuelve también el ETA estimado calculado con Haversine.
    Endpoint ligero, ideal para polling frecuente desde el mapa.
    """
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    # Verificar acceso
    es_cliente = await _verificar_cliente_del_servicio(db, servicio, current_usuario.id)
    es_admin = await _es_admin_taller(db, current_usuario.id, servicio.id_taller)
    if not es_cliente and not es_admin:
        raise HTTPException(status_code=403, detail="No tienes acceso a este servicio")

    # Última ubicación del técnico
    result = await db.execute(
        select(UbicacionTecnico)
        .where(UbicacionTecnico.id_servicio == servicio_id)
        .order_by(UbicacionTecnico.timestamp.desc())
        .limit(1)
    )
    ultima = result.scalar_one_or_none()

    if not ultima:
        raise HTTPException(
            status_code=404,
            detail="El técnico aún no ha compartido su ubicación"
        )

    # Ubicación del cliente para calcular ETA
    eta_info = None
    if servicio.id_solicitud_servicio:
        solicitud = await db.get(SolicitudServicio, servicio.id_solicitud_servicio)
        if solicitud and solicitud.ubicacion:
            point = to_shape(solicitud.ubicacion)
            eta_info = calcular_eta(
                float(ultima.latitud), float(ultima.longitud),
                point.y, point.x
            )

    return UbicacionTecnicoResponse(
        latitud=float(ultima.latitud),
        longitud=float(ultima.longitud),
        timestamp=ultima.timestamp,
        distancia_km=eta_info["distancia_km"] if eta_info else None,
        eta_minutos=eta_info["eta_minutos"] if eta_info else None,
        metodo_eta=eta_info["metodo"] if eta_info else None
    )


@router.get("/servicio/{servicio_id}/timeline", response_model=List[HistorialEstadoResponse])
async def obtener_timeline_servicio(
    servicio_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    [CLIENTE] Obtiene el historial completo de cambios de estado del servicio.
    Muestra cuándo salió el técnico, cuándo llegó, cuándo finalizó, etc.
    """
    servicio = await db.get(Servicio, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    es_cliente = await _verificar_cliente_del_servicio(db, servicio, current_usuario.id)
    es_admin = await _es_admin_taller(db, current_usuario.id, servicio.id_taller)
    if not es_cliente and not es_admin:
        raise HTTPException(status_code=403, detail="No tienes acceso a este servicio")

    result = await db.execute(
        select(HistorialEstadosServicio)
        .where(HistorialEstadosServicio.id_servicio == servicio_id)
        .order_by(HistorialEstadosServicio.fecha.asc())
    )
    historial = result.scalars().all()

    return [
        HistorialEstadoResponse(
            estado=h.estado.value,
            estado_descripcion=get_descripcion_estado(h.estado.value),
            fecha=h.fecha,
            tiempo_desde_anterior=float(h.tiempo_desde_anterior) if h.tiempo_desde_anterior else None
        )
        for h in historial
    ]
