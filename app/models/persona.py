from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Persona(Base):
    __tablename__ = "persona"

    # atributos
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True)
    nombre = Column(String(100), nullable=True)
    apellido_p = Column(String(100), nullable=True)
    apellido_m = Column(String(100), nullable=True)
    ci = Column(String(10), nullable=True)
    complemento = Column(String(2), nullable=True)
    telefono = Column(String(15), nullable=True)
    direccion = Column(String(255), nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, server_default="1")

    # relaciones
    tenant = relationship("Tenant")
    usuario = relationship("Usuario", back_populates="persona", uselist=False)
    dispositivos = relationship("DispositivoUsuario", back_populates="persona")
    sesiones = relationship("Sesion", back_populates="persona")
    vehiculos = relationship("Vehiculo", back_populates="persona")