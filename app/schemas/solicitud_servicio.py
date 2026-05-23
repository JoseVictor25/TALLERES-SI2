from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class TallerBasicInfo(BaseModel):
    id: int
    nombre: str
    telefono: str
    email: str
    puntos: float
    
    class Config:
        from_attributes = True


class SolicitudServicioResponse(BaseModel):
    id: int
    ubicacion: Optional[str] = None  # "lat,lon"
    fecha: datetime
    comentario: Optional[str] = None
    estado: str
    fecha_aceptada: Optional[datetime] = None
    costo_estimado: Optional[Decimal] = None
    sugerido_por: str
    id_taller: int
    id_diagnostico: int
    taller: Optional[TallerBasicInfo] = None
    
    class Config:
        from_attributes = True


class SolicitudServicioCreate(BaseModel):
    comentario: Optional[str] = Field(None, max_length=500)
    id_taller: int


class SolicitudServicioUpdate(BaseModel):
    estado: str
    costo_estimado: Optional[Decimal] = Field(None, ge=0)


class TallerSugeridoResponse(BaseModel):
    """Respuesta con taller y si ya tiene solicitud"""
    taller: TallerBasicInfo
    distancia_km: float
    tiene_solicitud: bool
    solicitud_id: Optional[int] = None
    especialidades_disponibles: list[str] = []
