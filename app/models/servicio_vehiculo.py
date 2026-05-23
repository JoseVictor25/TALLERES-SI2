from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ServicioVehiculo(Base):
    __tablename__ = "servicio_vehiculo"

    id_servicio = Column(
        Integer, 
        ForeignKey("servicio.id", ondelete="CASCADE"), 
        primary_key=True,
        nullable=False
    )
    id_vehiculo_taller = Column(
        Integer, 
        ForeignKey("vehiculo_taller.id", ondelete="RESTRICT"), 
        primary_key=True,
        nullable=False
    )

    # Relaciones
    servicio = relationship("Servicio", back_populates="vehiculos_asignados")
    vehiculo_taller = relationship("VehiculoTaller")
