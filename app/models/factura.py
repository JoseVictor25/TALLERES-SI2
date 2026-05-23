import enum
from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP, DECIMAL, String, Enum as SQLEnum, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class EstadoPago(str, enum.Enum):
    pendiente = "pendiente"
    pagado = "pagado"
    fallido = "fallido"
    reembolsado = "reembolsado"


class Factura(Base):
    __tablename__ = "factura"

    id = Column(Integer, primary_key=True, index=True)
    id_servicio = Column(Integer, ForeignKey("servicio.id", ondelete="RESTRICT"), nullable=False, index=True)
    monto_total = Column(DECIMAL(precision=10, scale=2), nullable=False)
    comision = Column(DECIMAL(precision=10, scale=2), nullable=False)
    liquido_taller = Column(DECIMAL(precision=10, scale=2), nullable=False)
    estado_pago = Column(SQLEnum(EstadoPago), nullable=False, default=EstadoPago.pendiente)
    metodo_pago = Column(String(50), nullable=True)
    id_pasarela = Column(String(255), nullable=True)
    url_qr = Column(String(1000), nullable=True)
    fecha_emision = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    fecha_pago = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relaciones
    servicio = relationship("Servicio", foreign_keys=[id_servicio])
