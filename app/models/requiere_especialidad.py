from sqlalchemy import Column, Integer, ForeignKey
from app.db.base_class import Base


class RequiereEspecialidad(Base):
    __tablename__ = "requiere_especialidad"

    id_categoria_incidente = Column(
        Integer,
        ForeignKey("categoria_incidente.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
    id_especialidad = Column(
        Integer,
        ForeignKey("especialidad.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
