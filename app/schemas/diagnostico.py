from pydantic import BaseModel, Field, root_validator
from typing import Optional, List, Any
from datetime import datetime


class EvidenciaResponse(BaseModel):
    id: int
    url: str
    transcripcion: Optional[str] = None
    tipo: str

    class Config:
        from_attributes = True


class IncidenteResponse(BaseModel):
    id_diagnostico: int
    id_tipo_incidente: int
    concepto: Optional[str] = None
    nivel_confianza: float
    sugerido_por: str

    @root_validator(pre=True)
    def extract_concepto(cls, values):
        # Si es un objeto ORM, extraer concepto de tipo_incidente
        if hasattr(values, '__dict__'):
            obj = values
            return {
                'id_diagnostico': obj.id_diagnostico,
                'id_tipo_incidente': obj.id_tipo_incidente,
                'concepto': obj.tipo_incidente.concepto if hasattr(obj, 'tipo_incidente') and obj.tipo_incidente else 'desconocido',
                'nivel_confianza': float(obj.nivel_confianza),
                'sugerido_por': obj.sugerido_por.value if hasattr(obj.sugerido_por, 'value') else str(obj.sugerido_por)
            }
        # Si ya es un dict, verificar si tiene concepto
        if isinstance(values, dict) and 'concepto' not in values:
            # Intentar obtener de tipo_incidente si existe
            if 'tipo_incidente' in values and values['tipo_incidente']:
                values['concepto'] = values['tipo_incidente'].get('concepto', 'desconocido')
        return values

    class Config:
        from_attributes = True


class DiagnosticoResponse(BaseModel):
    id: int
    descripcion: Optional[str]
    nivel_confianza: float
    fecha: datetime
    incidentes: List[IncidenteResponse] = []

    class Config:
        from_attributes = True


class SolicitudDiagnosticoResponse(BaseModel):
    id: int
    descripcion: Optional[str]
    fecha: datetime
    estado: str
    ubicacion: Optional[str]
    id_vehiculo: Optional[int]
    evidencias: List[EvidenciaResponse] = []
    diagnostico: Optional[DiagnosticoResponse] = None

    class Config:
        from_attributes = True
