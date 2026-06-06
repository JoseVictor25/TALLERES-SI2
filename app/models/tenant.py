from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Tenant(Base):
    __tablename__ = "tenant"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    codigo_acceso = Column(String(50), unique=True, index=True, nullable=True)
    estado_activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)

    # Relaciones
    talleres = relationship("Taller", back_populates="tenant")
    usuarios = relationship("Usuario", back_populates="tenant")
