from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum
from sqlalchemy import Enum as SQLEnum


class TipoEvidencia(str, enum.Enum):
    audio = "audio"
    imagen = "imagen"


class Evidencia(Base):
    __tablename__ = "evidencia"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text, nullable=False)
    transcripcion = Column(Text, nullable=True)
    tipo = Column(SQLEnum(TipoEvidencia), nullable=False)
    id_solicitud_diagnostico = Column(Integer, ForeignKey("solicitud_diagnostico.id", ondelete="CASCADE"), nullable=False)

    solicitud = relationship("SolicitudDiagnostico", back_populates="evidencias")
