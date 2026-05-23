from sqlalchemy import Column, Integer, ForeignKey, DECIMAL, CheckConstraint
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum
from sqlalchemy import Enum as SQLEnum


class SugeridoPor(str, enum.Enum):
    ia = "ia"
    conductor = "conductor"


class Incidente(Base):
    __tablename__ = "incidente"

    id_diagnostico = Column(Integer, ForeignKey("diagnostico.id", ondelete="CASCADE"), primary_key=True)
    id_tipo_incidente = Column(Integer, ForeignKey("tipo_incidente.id", ondelete="RESTRICT"), primary_key=True)
    sugerido_por = Column(SQLEnum(SugeridoPor), nullable=False)
    nivel_confianza = Column(DECIMAL(5,4), nullable=False)

    diagnostico = relationship("Diagnostico", back_populates="incidentes")
    tipo_incidente = relationship("TipoIncidente", back_populates="incidentes")

    __table_args__ = (
        CheckConstraint('nivel_confianza >= 0 AND nivel_confianza <= 1', name='check_nivel_confianza_incidente'),
    )
