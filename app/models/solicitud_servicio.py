from sqlalchemy import Column, Integer, ForeignKey, DECIMAL, Text, TIMESTAMP, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from app.db.base_class import Base
import enum
from sqlalchemy import Enum as SQLEnum
from datetime import datetime


class SugeridoPorTipo(str, enum.Enum):
    ia = "ia"
    conductor = "conductor"


class EstadoSolicitudServicio(str, enum.Enum):
    pendiente = "pendiente"
    aceptada = "aceptada"
    rechazada = "rechazada"
    cancelada = "cancelada"
    expirada = "expirada"


class SolicitudServicio(Base):
    __tablename__ = "solicitud_servicio"

    id = Column(Integer, primary_key=True, index=True)
    ubicacion = Column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    fecha = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    comentario = Column(Text, nullable=True)
    estado = Column(SQLEnum(EstadoSolicitudServicio), nullable=False, default=EstadoSolicitudServicio.pendiente)
    fecha_aceptada = Column(TIMESTAMP, nullable=True)
    costo_estimado = Column(DECIMAL(10, 2), nullable=True)
    distancia_km = Column(DECIMAL(10, 2), nullable=True)
    sugerido_por = Column(SQLEnum(SugeridoPorTipo), nullable=False)
    id_taller = Column(Integer, ForeignKey("taller.id", ondelete="RESTRICT"), nullable=False)
    id_diagnostico = Column(Integer, ForeignKey("diagnostico.id", ondelete="RESTRICT"), nullable=False)

    # Relaciones
    taller = relationship("Taller", back_populates="solicitudes_servicio")
    diagnostico = relationship("Diagnostico", back_populates="solicitudes_servicio")
    servicio = relationship("Servicio", back_populates="solicitud_servicio", uselist=False)

    # Constraints
    __table_args__ = (
        UniqueConstraint('id_taller', 'id_diagnostico', name='uq_solicitud_taller_diagnostico'),
        CheckConstraint('costo_estimado >= 0', name='check_costo_estimado_positivo'),
    )
