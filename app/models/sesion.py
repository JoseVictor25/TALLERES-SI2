from sqlalchemy import Column, Integer, Text, TIMESTAMP, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Sesion(Base):
    __tablename__ = "sesion"

    # atributos
    id = Column(Integer, primary_key=True, index=True)
    token = Column(Text, nullable=False, unique=True)
    fecha_inicio = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    fecha_expira = Column(TIMESTAMP(timezone=True), nullable=False)
    activa = Column(Boolean, nullable=False, default=True)
    id_persona = Column(Integer, ForeignKey("persona.id", ondelete="CASCADE"), nullable=False)

    # relaciones
    persona = relationship("Persona", back_populates="sesiones")