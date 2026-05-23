from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Rol(Base):
    __tablename__ = "rol"

    # atributos
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), unique=True, nullable=False)

    # relaciones
    usuarios = relationship("RolUsuario", back_populates="rol")
    permisos = relationship("RolPermiso", back_populates="rol")