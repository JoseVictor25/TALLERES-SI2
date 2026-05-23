from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ServicioTecnico(Base):
    __tablename__ = "servicio_tecnico"

    id_servicio = Column(
        Integer, 
        ForeignKey("servicio.id", ondelete="CASCADE"), 
        primary_key=True,
        nullable=False
    )
    id_empleado = Column(
        Integer, 
        ForeignKey("empleado.id", ondelete="RESTRICT"), 
        primary_key=True,
        nullable=False
    )

    # Relaciones
    servicio = relationship("Servicio", back_populates="tecnicos_asignados")
    empleado = relationship("Empleado")
