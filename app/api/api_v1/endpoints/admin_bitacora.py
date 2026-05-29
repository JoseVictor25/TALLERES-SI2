from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from app.core.deps import get_current_usuario
from app.db.session import get_db
from app.models.usuario import Usuario
from app.models.bitacora_acceso import BitacoraAcceso
from app.schemas.admin_bitacora import BitacoraListResponse

router = APIRouter()

@router.get("", response_model=BitacoraListResponse)
async def list_bitacora(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_usuario)
):
    query = select(BitacoraAcceso)
    if search:
        query = query.filter(
            BitacoraAcceso.email_intentado.ilike(f"%{search}%") |
            BitacoraAcceso.ip_address.ilike(f"%{search}%") |
            BitacoraAcceso.accion.ilike(f"%{search}%")
        )
    
    # Obtener el total
    total_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(total_query)

    # Obtener los items paginados
    query = query.order_by(desc(BitacoraAcceso.fecha_hora)).offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return BitacoraListResponse(items=list(items), total=total or 0, skip=skip, limit=limit)
