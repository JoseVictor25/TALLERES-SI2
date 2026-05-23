# app/models/taller.py
from sqlalchemy import Column, Integer, Text, String, Time, DECIMAL, ForeignKey, CheckConstraint, Enum, Index
from geoalchemy2 import Geography
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class EstadoTaller(str, enum.Enum):
    activo = "activo"
    suspendido = "suspendido"

class Taller(Base):
    __tablename__ = "taller"

    # atributos
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    ubicacion = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    telefono = Column(String(15), nullable=False)
    email = Column(String(255), nullable=False)
    hora_inicio = Column(Time, nullable=True)
    hora_fin = Column(Time, nullable=True)
    url_web = Column(Text, nullable=True)
    puntos = Column(DECIMAL(3,2), nullable=False, default=0.00)
    estado = Column(Enum(EstadoTaller), nullable=False, default=EstadoTaller.activo)
    id_solicitud_afiliacion = Column(Integer, ForeignKey("solicitud_afiliacion.id", ondelete="RESTRICT"), nullable=False, unique=True)

    # Relaciones
    solicitud = relationship("SolicitudAfiliacion", back_populates="taller")
    solicitudes_servicio = relationship("SolicitudServicio", back_populates="taller")
    servicios = relationship("Servicio", back_populates="taller")

    # restricciones
    __table_args__ = (
        CheckConstraint('puntos >= 0 AND puntos <= 5', name='check_puntos'),
        CheckConstraint('hora_fin > hora_inicio', name='check_horario'),
    )