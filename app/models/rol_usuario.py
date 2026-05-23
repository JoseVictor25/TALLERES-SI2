from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class RolUsuario(Base):
    __tablename__ = "rol_usuario"

    # atributos
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False)
    id_rol = Column(Integer, ForeignKey("rol.id", ondelete="RESTRICT"), nullable=False)
    id_taller = Column(Integer, ForeignKey("taller.id", ondelete="CASCADE"), nullable=True)

    # relaciones
    usuario = relationship("Usuario", back_populates="roles")
    rol = relationship("Rol", back_populates="usuarios")
    taller = relationship("Taller")