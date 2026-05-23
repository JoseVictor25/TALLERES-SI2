from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP, Boolean, DECIMAL, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class EmpleadoUbicacion(Base):
    __tablename__ = "empleado_ubicacion"

    id = Column(Integer, primary_key=True, index=True)
    id_empleado = Column(Integer, ForeignKey("empleado.id", ondelete="CASCADE"), nullable=False)
    latitud = Column(DECIMAL(10, 8), nullable=False)
    longitud = Column(DECIMAL(11, 8), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    activa = Column(Boolean, nullable=False, default=True)
    id_servicio = Column(Integer, ForeignKey("servicio.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    empleado = relationship("Empleado", back_populates="ubicaciones")
    servicio = relationship("Servicio", back_populates="ubicaciones_tecnicos")
