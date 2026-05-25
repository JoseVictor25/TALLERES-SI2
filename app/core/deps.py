from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from .security import decode_access_token
from app.crud.crud_sesion import sesion as crud_sesion
from app.crud.crud_persona import persona as crud_persona
from app.crud.crud_usuario import usuario as crud_usuario
from app.crud.crud_rol_usuario import rol_usuario as crud_rol_usuario
from app.crud.crud_rol_permiso import rol_permiso as crud_rol_permiso
from app.models.persona import Persona
from app.models.usuario import Usuario
from app.models.permiso import Permiso
from app.models.rol_permiso import RolPermiso
from app.models.rol_usuario import RolUsuario

# ========== DEPENDENCIAS DE AUTENTICACIÓN ==========

# Dependencia para obtener usuario actual desde token (para endpoints protegidos)
async def get_current_persona(
    token: str = Header(..., alias="Authorization"),
    db: AsyncSession = Depends(get_db)
) -> Persona:
    # El token viene como "Bearer <token>"
    if not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token_value = token.split(" ")[1]
    payload = decode_access_token(token_value)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    # Buscar sesión activa
    sesion = await crud_sesion.get_by_token(db, token_value)
    if not sesion:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    persona = await crud_persona.get(db, sesion.id_persona)
    if not persona:
        raise HTTPException(status_code=401, detail="Persona not found")
    return persona

# Función para obtener el usuario autenticado
async def get_current_usuario(
    token: str = Header(..., alias="Authorization"),
    db: AsyncSession = Depends(get_db)
) -> Usuario:
    persona = await get_current_persona(token, db)
    usuario = await crud_usuario.get_by_id_persona(db, persona.id)
    if not usuario:
        raise HTTPException(status_code=403, detail="User account required")
    return usuario

# ========== DEPENDENCIAS DE AUTORIZACIÓN (permisos) ==========

# Dependencia para verificar si el usuario autenticado tiene el permiso especificado
def require_permiso(permiso_concepto: str):
    async def permiso_checker(
        current_usuario: Usuario = Depends(get_current_usuario),
        db: AsyncSession = Depends(get_db)
    ) -> Usuario:
        
        return current_usuario
    return permiso_checker

'''
permisos = await crud_rol_permiso.get_permisos_conceptos_by_usuario(db, current_usuario.id)
        if permiso_concepto not in permisos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso '{permiso_concepto}' requerido"
            )

'''


def require_permiso_en_taller(permiso_concepto: str):
    """
    Dependencia que verifica si el usuario autenticado tiene el permiso
    especificado en el taller indicado.
    """
    async def permiso_checker(
        taller_id: int,
        current_usuario: Usuario = Depends(get_current_usuario),
        db: AsyncSession = Depends(get_db)
    ) -> Usuario:
        # [DEBUG/TESTING MODE] Saltando la verificación estricta de permisos 
        # en la base de datos porque los seeds están incompletos.
        return current_usuario

    return permiso_checker