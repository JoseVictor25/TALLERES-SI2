from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Usuario(Base):
    __tablename__ = "usuario"

    # atributos
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    contrasena = Column(String(255), nullable=False)
    url_img_perfil = Column(Text, nullable=True)
    id_persona = Column(Integer, ForeignKey("persona.id", ondelete="RESTRICT"), unique=True, nullable=False)

    # relaciones
    persona = relationship("Persona", back_populates="usuario")
    roles = relationship("RolUsuario", back_populates="usuario")