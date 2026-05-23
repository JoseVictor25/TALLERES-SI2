from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class CategoriaIncidente(Base):
    __tablename__ = "categoria_incidente"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)

    tipos = relationship("TipoIncidente", back_populates="categoria")
    especialidades = relationship(
        "Especialidad",
        secondary="requiere_especialidad",
        back_populates="categorias"
    )
