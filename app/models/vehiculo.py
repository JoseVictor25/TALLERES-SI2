from sqlalchemy import Column, Integer, String, SmallInteger, Enum, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class TipoVehiculo(str, enum.Enum):
    auto = "auto"
    camioneta = "camioneta"
    moto = "moto"
    camion = "camion"
    microbus = "microbus"
    otro = "otro"

class Vehiculo(Base):
    __tablename__ = "vehiculo"

    # atributos
    id = Column(Integer, primary_key=True, index=True)
    matricula = Column(String(20), nullable=False, unique=True)
    marca = Column(String(100), nullable=False)
    modelo = Column(String(100), nullable=False)
    anio = Column(SmallInteger, nullable=False)
    color = Column(String(50), nullable=True)
    tipo = Column(Enum(TipoVehiculo), nullable=False)
    id_persona = Column(Integer, ForeignKey("persona.id", ondelete="RESTRICT"), nullable=False)

    # relaciones
    persona = relationship("Persona", back_populates="vehiculos") 

    # restricciones
    __table_args__ = (
        CheckConstraint('anio >= 1900 AND anio <= 2100', name='check_anio'),
    )