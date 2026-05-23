from sqlalchemy import Column, Integer, String, ForeignKey, Enum, CheckConstraint, TIMESTAMP, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class EstadoEmpleado(str, enum.Enum):
    activo = "activo"
    disponible = "disponible"
    en_servicio = "en_servicio"
    suspendido = "suspendido"

class Empleado(Base):
    __tablename__ = "empleado"

    id = Column(Integer, primary_key=True, index=True)
    fecha_ingreso = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    fecha_salida = Column(TIMESTAMP(timezone=True), nullable=True)
    estado = Column(Enum(EstadoEmpleado), nullable=False, default=EstadoEmpleado.activo)
    id_usuario = Column(Integer, ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False)
    id_taller = Column(Integer, ForeignKey("taller.id", ondelete="RESTRICT"), nullable=False)

    usuario = relationship("Usuario", backref="empleados")
    taller = relationship("Taller", backref="empleados")
    ubicaciones = relationship("EmpleadoUbicacion", back_populates="empleado", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint('fecha_salida IS NULL OR fecha_salida >= fecha_ingreso', name='chk_fechas_empleado'),
    )