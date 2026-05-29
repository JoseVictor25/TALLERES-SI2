from pydantic import BaseModel, EmailStr
from typing import List, Optional

class UsuarioAdminResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    nombre_completo: str
    ci: Optional[str] = None
    roles: List[str]
    is_active: bool

class UsuarioAdminListResponse(BaseModel):
    items: List[UsuarioAdminResponse]
    total: int
    skip: int
    limit: int
