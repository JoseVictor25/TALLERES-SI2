from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ConfiguracionSistema(Base):
    __tablename__ = "configuracion_sistema"

    id = Column(Integer, primary_key=True, index=True)
    clave = Column(String(100), nullable=False, unique=True)
    valor = Column(Text, nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False)

    usuario = relationship("Usuario")
