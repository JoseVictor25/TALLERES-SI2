from sqlalchemy import Column, Integer, ForeignKey, Interval
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Metrica(Base):
    __tablename__ = "metrica"

    id = Column(Integer, primary_key=True, index=True)
    tiempo_respuesta = Column(Interval, nullable=True)  # desde creación de solicitud hasta aceptación del taller
    tiempo_llegada = Column(Interval, nullable=True)    # desde aceptación hasta marca "en_lugar"
    tiempo_resolucion = Column(Interval, nullable=True) # desde "en_lugar" hasta "finalizado"
    id_servicio = Column(Integer, ForeignKey("servicio.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Relaciones
    servicio = relationship("Servicio", back_populates="metrica", uselist=False)
