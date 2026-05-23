from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Permiso(Base):
    __tablename__ = "permiso"

    id = Column(Integer, primary_key=True, index=True)
    concepto = Column(String(100), unique=True, nullable=False)

    roles = relationship("RolPermiso", back_populates="permiso")