import enum
from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP, Text, Boolean, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Mensaje(Base):
    __tablename__ = "mensaje"

    id = Column(Integer, primary_key=True, index=True)
    id_servicio = Column(Integer, ForeignKey("servicio.id", ondelete="CASCADE"), nullable=False, index=True)
    id_remitente = Column(Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    texto = Column(Text, nullable=False)
    tiempo = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    leido = Column(Boolean, nullable=False, default=False)

    # Relaciones
    servicio = relationship("Servicio", foreign_keys=[id_servicio])
    remitente = relationship("Usuario", foreign_keys=[id_remitente])
