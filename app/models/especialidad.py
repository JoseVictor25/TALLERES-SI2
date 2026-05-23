from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Especialidad(Base):
    __tablename__ = "especialidad"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    descripcion = Column(Text, nullable=True)
    
    categorias = relationship(
        "CategoriaIncidente",
        secondary="requiere_especialidad",
        back_populates="especialidades"
    )