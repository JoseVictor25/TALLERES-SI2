from pydantic import BaseModel, Field
from typing import Optional


class ValoracionCreate(BaseModel):
    """Schema para crear una valoración"""
    puntos: int = Field(..., ge=1, le=5, description="Puntuación de 1 a 5 estrellas")
    comentario: Optional[str] = Field(None, description="Comentario opcional del cliente")


class ValoracionResponse(BaseModel):
    """Schema de respuesta de valoración"""
    id: int
    puntos: int
    comentario: Optional[str]
    id_servicio: int
    
    class Config:
        from_attributes = True


class ValoracionUpdate(BaseModel):
    """Schema para actualizar una valoración"""
    puntos: Optional[int] = Field(None, ge=1, le=5)
    comentario: Optional[str] = None
