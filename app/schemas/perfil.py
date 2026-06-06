from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

class UpdatePerfilRequest(BaseModel):
    username: Optional[str] = None
    url_img_perfil: Optional[str] = None
    nombre: Optional[str] = None
    apellido_p: Optional[str] = None
    apellido_m: Optional[str] = None
    ci: Optional[str] = None
    complemento: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None

class PerfilResponse(BaseModel):
    id_usuario: Optional[int] = None
    email: EmailStr
    username: Optional[str] = None
    url_img_perfil: Optional[str] = None
    nombre: Optional[str] = None
    apellido_p: Optional[str] = None
    apellido_m: Optional[str] = None
    ci: Optional[str] = None
    complemento: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    roles: List[str] = []  # Lista de roles del usuario
    tenant_id: Optional[int] = None

class CreateUsuarioRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class RequestPasswordChangeRequest(BaseModel):
    email: EmailStr

class ChangePasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str = Field(..., min_length=6)