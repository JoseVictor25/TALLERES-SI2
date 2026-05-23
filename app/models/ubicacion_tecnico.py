from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP, DECIMAL, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class UbicacionTecnico(Base):
    __tablename__ = "ubicacion_tecnico"

    id = Column(Integer, primary_key=True, index=True)
    id_servicio = Column(Integer, ForeignKey("servicio.id", ondelete="CASCADE"), nullable=False, index=True)
    id_empleado = Column(Integer, ForeignKey("empleado.id", ondelete="CASCADE"), nullable=False)
    latitud = Column(DECIMAL(precision=10, scale=7), nullable=False)
    longitud = Column(DECIMAL(precision=10, scale=7), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relaciones
    servicio = relationship("Servicio", foreign_keys=[id_servicio])
    empleado = relationship("Empleado", foreign_keys=[id_empleado])
