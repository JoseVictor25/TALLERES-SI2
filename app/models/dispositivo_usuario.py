from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class DispositivoUsuario(Base):
    __tablename__ = "dispositivo_usuario"

    # atributos
    id = Column(Integer, primary_key=True, index=True)
    token_fcm = Column(Text, nullable=False)
    id_persona = Column(Integer, ForeignKey("persona.id", ondelete="CASCADE"), nullable=False)

    # relaciones
    persona = relationship("Persona", back_populates="dispositivos")