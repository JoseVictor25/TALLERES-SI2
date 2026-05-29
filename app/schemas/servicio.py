from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ============================================================
# SCHEMAS PARA TÉCNICOS Y VEHÍCULOS
# ============================================================

class TecnicoDisponibleResponse(BaseModel):
    id: int
    nombre_completo: str
    especialidades: List[str] = []
    estado: str
    
    class Config:
        from_attributes = True


class VehiculoTallerDisponibleResponse(BaseModel):
    id: int
    matricula: str
    marca: str
    modelo: str
    tipo: str
    estado: str
    
    class Config:
        from_attributes = True


# ============================================================
# SCHEMAS PARA SERVICIO
# ============================================================

class TecnicoAsignadoResponse(BaseModel):
    id_empleado: int
    nombre_completo: str
    
    class Config:
        from_attributes = True


class VehiculoAsignadoResponse(BaseModel):
    id_vehiculo_taller: int
    matricula: str
    marca: str
    modelo: str
    
    class Config:
        from_attributes = True


class ServicioResponse(BaseModel):
    id: int
    fecha: datetime
    estado: str
    id_taller: int
    id_solicitud_servicio: Optional[int] = None
    tecnicos_asignados: List[TecnicoAsignadoResponse] = []
    vehiculos_asignados: List[VehiculoAsignadoResponse] = []
    
    class Config:
        from_attributes = True


class ServicioCreate(BaseModel):
    id_solicitud_servicio: int
    tecnicos_ids: List[int]
    vehiculos_ids: List[int]


# ============================================================
# SCHEMAS PARA SOLICITUDES (VISTA TALLER)
# ============================================================

class EvidenciaDetalleResponse(BaseModel):
    id: int
    url: str
    tipo: str
    transcripcion: Optional[str] = None
    
    class Config:
        from_attributes = True


class VehiculoClienteResponse(BaseModel):
    matricula: str
    marca: str
    modelo: str
    anio: int
    color: Optional[str] = None
    tipo: Optional[str] = None
    
    class Config:
        from_attributes = True


class DiagnosticoDetalleResponse(BaseModel):
    id: int
    descripcion: Optional[str] = None
    nivel_confianza: float
    fecha: datetime
    
    class Config:
        from_attributes = True


class SolicitudServicioDetalleResponse(BaseModel):
    """Schema completo para mostrar al administrador del taller"""
    id: int
    ubicacion: Optional[str] = None  # "lat,lon"
    fecha: datetime
    comentario: Optional[str] = None
    estado: str
    sugerido_por: str
    distancia_km: Optional[float] = None
    
    # Información del diagnóstico
    diagnostico: Optional[DiagnosticoDetalleResponse] = None
    
    # Información del vehículo del cliente
    vehiculo_cliente: Optional[VehiculoClienteResponse] = None
    
    # Evidencias (fotos, audio)
    evidencias: List[EvidenciaDetalleResponse] = []
    
    # Descripción del conductor
    descripcion_conductor: Optional[str] = None
    
    class Config:
        from_attributes = True


class SolicitudServicioListResponse(BaseModel):
    """Schema resumido para listar solicitudes"""
    id: int
    fecha: datetime
    estado: str
    sugerido_por: str
    distancia_km: Optional[float] = None
    comentario: Optional[str] = None
    tiene_servicio: bool = False
    
    class Config:
        from_attributes = True


# ============================================================
# SCHEMAS PARA CLIENTE (VISTA MÓVIL)
# ============================================================

class TallerInfoResponse(BaseModel):
    """Información básica del taller para el cliente"""
    id: int
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None
    ubicacion: Optional[str] = None  # "lat,lon"
    puntos: float
    
    class Config:
        from_attributes = True


class ServicioClienteResponse(BaseModel):
    """Schema completo del servicio para el cliente móvil"""
    id: int
    fecha: datetime
    estado: str
    
    # Información del taller
    taller: TallerInfoResponse
    
    # Técnicos asignados
    tecnicos_asignados: List[TecnicoAsignadoResponse] = []
    
    # Vehículos del taller asignados
    vehiculos_asignados: List[VehiculoAsignadoResponse] = []
    
    # Ubicación del cliente (de la solicitud original)
    ubicacion_cliente: Optional[str] = None  # "lat,lon"
    
    # Información del diagnóstico
    diagnostico: Optional[DiagnosticoDetalleResponse] = None
    
    class Config:
        from_attributes = True


class ServicioClienteListResponse(BaseModel):
    """Schema resumido para listar servicios del cliente"""
    id: int
    fecha: datetime
    estado: str
    taller_nombre: str
    diagnostico_descripcion: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============================================================
# SCHEMAS PARA SEGUIMIENTO EN TIEMPO REAL (CLIENTE MÓVIL)
# ============================================================

class TecnicoUbicacionResponse(BaseModel):
    """Ubicación en tiempo real de un técnico asignado"""
    id_empleado: int
    nombre_completo: str
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    timestamp: Optional[datetime] = None
    tiene_ubicacion: bool

    class Config:
        from_attributes = True


class EstadoHistorialClienteResponse(BaseModel):
    """Un estado en el historial de un servicio"""
    estado: str
    estado_descripcion: str
    tiempo: datetime

    class Config:
        from_attributes = True


class ServicioSeguimientoClienteResponse(BaseModel):
    """Schema completo de seguimiento del servicio para el cliente móvil.
    Incluye historial de estados y ubicaciones de técnicos en tiempo real."""
    id: int
    fecha: datetime
    estado: str
    estado_descripcion: str

    # Información del taller
    taller: TallerInfoResponse

    # Técnicos con su ubicación GPS actual
    tecnicos: List[TecnicoUbicacionResponse] = []

    # Historial de cambios de estado
    historial_estados: List[EstadoHistorialClienteResponse] = []

    # Ubicación del cliente (de la solicitud original) "lat,lon"
    ubicacion_cliente: Optional[str] = None

    # Descripción del diagnóstico
    diagnostico_descripcion: Optional[str] = None

    class Config:
        from_attributes = True
