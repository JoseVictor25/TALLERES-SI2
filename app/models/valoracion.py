from sqlalchemy import Column, Integer, Text, SmallInteger, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Valoracion(Base):
    __tablename__ = "valoracion"

    id = Column(Integer, primary_key=True, index=True)
    comentario = Column(Text, nullable=True)
    puntos = Column(SmallInteger, nullable=False)
    id_servicio = Column(Integer, ForeignKey("servicio.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Relaciones
    servicio = relationship("Servicio", back_populates="valoracion")

    # Restricciones
    __table_args__ = (
        CheckConstraint('puntos >= 1 AND puntos <= 5', name='check_puntos_valoracion'),
    )
