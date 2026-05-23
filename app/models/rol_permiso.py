from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class RolPermiso(Base):
    __tablename__ = "rol_permiso"

    # atributos
    id_rol = Column(Integer, ForeignKey("rol.id", ondelete="CASCADE"), primary_key=True)
    id_permiso = Column(Integer, ForeignKey("permiso.id", ondelete="CASCADE"), primary_key=True)

    # relaciones
    rol = relationship("Rol", back_populates="permisos")
    permiso = relationship("Permiso", back_populates="roles")