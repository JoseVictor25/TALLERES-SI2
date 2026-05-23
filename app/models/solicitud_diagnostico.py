from sqlalchemy import Column, Integer, Text, TIMESTAMP, Enum as SQLEnum, ForeignKey, func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from app.db.base_class import Base
import enum


class EstadoSolicitudDiagnostico(str, enum.Enum):
    pendiente = "pendiente"
    diagnosticada = "diagnosticada"
    cancelada = "cancelada"
    error = "error"


class SolicitudDiagnostico(Base):
    __tablename__ = "solicitud_diagnostico"

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(Text, nullable=True)
    fecha = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    estado = Column(SQLEnum(EstadoSolicitudDiagnostico), nullable=False, default=EstadoSolicitudDiagnostico.pendiente)
    ubicacion = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    id_persona = Column(Integer, ForeignKey("persona.id", ondelete="RESTRICT"), nullable=False)
    id_vehiculo = Column(Integer, ForeignKey("vehiculo.id", ondelete="SET NULL"), nullable=True)

    evidencias = relationship("Evidencia", back_populates="solicitud", cascade="all, delete-orphan")
    diagnostico = relationship("Diagnostico", back_populates="solicitud", uselist=False)
