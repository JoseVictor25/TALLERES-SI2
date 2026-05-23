from sqlalchemy import Column, Integer, String, SmallInteger, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class TipoIncidente(Base):
    __tablename__ = "tipo_incidente"

    id = Column(Integer, primary_key=True, index=True)
    concepto = Column(String(150), nullable=False, unique=True)
    prioridad = Column(SmallInteger, nullable=False)
    requiere_remolque = Column(Boolean, nullable=False, default=False)
    id_categoria_incidente = Column(Integer, ForeignKey("categoria_incidente.id", ondelete="SET NULL"), nullable=True)

    categoria = relationship("CategoriaIncidente", back_populates="tipos")
    incidentes = relationship("Incidente", back_populates="tipo_incidente")

    __table_args__ = (
        CheckConstraint('prioridad BETWEEN 1 AND 5', name='check_prioridad_tipo_incidente'),
    )
