from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from sqlalchemy import Enum as SQLEnum
from app.models.servicio import EstadoServicio


class HistorialEstadoServicio(Base):
    __tablename__ = "historial_estados_servicio"

    id = Column(Integer, primary_key=True, index=True)
    estado = Column(SQLEnum(EstadoServicio), nullable=False)
    tiempo = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    id_servicio = Column(Integer, ForeignKey("servicio.id", ondelete="CASCADE"), nullable=False)

    # Relaciones
    servicio = relationship("Servicio", back_populates="historial_estados")
