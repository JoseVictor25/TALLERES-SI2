from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.deps import get_current_usuario
from app.db.session import get_db
from app.schemas.admin_usuarios import UsuarioAdminListResponse, UsuarioAdminResponse
from app.services.admin_usuarios_service import list_usuarios_admin, toggle_usuario_status
from app.models.usuario import Usuario

router = APIRouter()

@router.get("/", response_model=UsuarioAdminListResponse)
async def list_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_usuario)
):
    items, total = await list_usuarios_admin(db, skip, limit, search)
    return UsuarioAdminListResponse(items=items, total=total, skip=skip, limit=limit)

@router.put("/{id_usuario}/toggle-status", response_model=UsuarioAdminResponse)
async def toggle_status(
    id_usuario: int = Path(..., title="The ID of the user to toggle"),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_usuario)
):
    return await toggle_usuario_status(db, id_usuario)
