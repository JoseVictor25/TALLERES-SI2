from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class BitacoraResponse(BaseModel):
    id: int
    id_usuario: Optional[int] = None
    email_intentado: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    accion: str
    exito: bool
    fecha_hora: datetime

    model_config = ConfigDict(from_attributes=True)

class BitacoraListResponse(BaseModel):
    items: List[BitacoraResponse]
    total: int
    skip: int
    limit: int
