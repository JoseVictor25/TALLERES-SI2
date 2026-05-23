# app/models/solicitud_afiliacion.py
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, Enum, func, Index
from geoalchemy2 import Geography
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class EstadoSolicitudAfiliacion(str, enum.Enum):
    pendiente = "pendiente"
    aprobada = "aprobada"
    rechazada = "rechazada"

class SolicitudAfiliacion(Base):
    __tablename__ = "solicitud_afiliacion"

    # atributos
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    ubicacion = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    telefono = Column(String(15), nullable=False)
    email = Column(String(255), nullable=False)
    comentario = Column(Text, nullable=True)
    fecha = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    fecha_revision = Column(TIMESTAMP(timezone=True), nullable=True)
    estado = Column(Enum(EstadoSolicitudAfiliacion), nullable=False, default=EstadoSolicitudAfiliacion.pendiente)
    comentario_revision = Column(Text, nullable=True)
    id_usuario_solicita = Column(Integer, ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False)
    id_usuario_revisa = Column(Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    usuario_solicita = relationship("Usuario", foreign_keys=[id_usuario_solicita])
    usuario_revisa = relationship("Usuario", foreign_keys=[id_usuario_revisa])
    taller = relationship("Taller", back_populates="solicitud", uselist=False)