from pydantic import BaseModel
from typing import Optional, List

class ConfiguracionBase(BaseModel):
    clave: str
    valor: str

class ConfiguracionCreate(ConfiguracionBase):
    pass

class ConfiguracionUpdate(BaseModel):
    valor: str

class ConfiguracionResponse(BaseModel):
    id: int
    clave: str
    valor: str
    id_usuario: int

    class Config:
        from_attributes = True

class ConfiguracionListResponse(BaseModel):
    items: List[ConfiguracionResponse]
    total: int
    skip: int
    limit: int
