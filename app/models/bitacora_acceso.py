import enum
from sqlalchemy import Column, Integer, String, TIMESTAMP, Boolean, Enum, func, Text
from app.db.base_class import Base

class AccionAcceso(str, enum.Enum):
    LOGIN_EXITOSO = "LOGIN_EXITOSO"
    LOGIN_FALLIDO = "LOGIN_FALLIDO"
    LOGOUT = "LOGOUT"

class BitacoraAcceso(Base):
    __tablename__ = "bitacora_acceso"

    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, index=True, nullable=True) # Puede ser nulo si el login falla y el usuario no existe
    email_intentado = Column(String(255), nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    accion = Column(Enum(AccionAcceso), nullable=False)
    exito = Column(Boolean, nullable=False)
    fecha_hora = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
