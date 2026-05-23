from sqlalchemy import Column, Integer, Text, DECIMAL, TIMESTAMP, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Diagnostico(Base):
    __tablename__ = "diagnostico"

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(Text, nullable=True)
    nivel_confianza = Column(DECIMAL(5,4), nullable=False)
    fecha = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    id_solicitud_diagnostico = Column(Integer, ForeignKey("solicitud_diagnostico.id", ondelete="CASCADE"), nullable=False, unique=True)

    solicitud = relationship("SolicitudDiagnostico", back_populates="diagnostico")
    incidentes = relationship("Incidente", back_populates="diagnostico", cascade="all, delete-orphan")
    solicitudes_servicio = relationship("SolicitudServicio", back_populates="diagnostico")

    __table_args__ = (
        CheckConstraint('nivel_confianza >= 0 AND nivel_confianza <= 1', name='check_nivel_confianza_diagnostico'),
    )
