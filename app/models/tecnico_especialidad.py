from sqlalchemy import Column, Integer, ForeignKey
from app.db.base_class import Base

class TecnicoEspecialidad(Base):
    __tablename__ = "tecnico_especialidad"
    id_empleado = Column(Integer, ForeignKey("empleado.id", ondelete="CASCADE"), primary_key=True)
    id_especialidad = Column(Integer, ForeignKey("especialidad.id", ondelete="RESTRICT"), primary_key=True)