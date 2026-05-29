from typing import Tuple, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from fastapi import HTTPException

from app.models.usuario import Usuario
from app.models.persona import Persona
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol
from app.schemas.admin_usuarios import UsuarioAdminResponse

async def list_usuarios_admin(
    db: AsyncSession, skip: int = 0, limit: int = 10, search: Optional[str] = None
) -> Tuple[List[UsuarioAdminResponse], int]:
    query = select(
        Usuario.id,
        Usuario.nombre.label('username'),
        Usuario.is_active,
        Persona.email,
        Persona.nombre.label('persona_nombre'),
        Persona.apellido_p,
        Persona.apellido_m,
        Persona.ci
    ).join(Persona, Usuario.id_persona == Persona.id)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Usuario.nombre.ilike(search_term),
                Persona.email.ilike(search_term),
                Persona.nombre.ilike(search_term),
                Persona.apellido_p.ilike(search_term),
                Persona.ci.ilike(search_term)
            )
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    items = []
    for row in rows:
        # Get roles for user
        roles_query = select(Rol.nombre).join(RolUsuario, RolUsuario.id_rol == Rol.id).where(RolUsuario.id_usuario == row.id)
        roles_result = await db.execute(roles_query)
        roles = [r[0] for r in roles_result.all()]

        # Construct full name
        nombres_parts = [p for p in (row.persona_nombre, row.apellido_p, row.apellido_m) if p]
        nombre_completo = " ".join(nombres_parts) if nombres_parts else "Sin nombre"

        items.append(UsuarioAdminResponse(
            id=row.id,
            username=row.username,
            email=row.email,
            nombre_completo=nombre_completo,
            ci=row.ci,
            roles=roles,
            is_active=row.is_active
        ))

    return items, total

async def toggle_usuario_status(db: AsyncSession, id_usuario: int) -> UsuarioAdminResponse:
    result = await db.execute(select(Usuario).where(Usuario.id == id_usuario))
    usuario = result.scalar_one_or_none()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    usuario.is_active = not usuario.is_active
    await db.commit()
    
    # Return updated user logic
    # Just need a simplified version to return
    # The frontend only cares that it succeeded, but we should return the new object.
    
    # To return full object, we fetch persona
    result_persona = await db.execute(select(Persona).where(Persona.id == usuario.id_persona))
    persona = result_persona.scalar_one_or_none()
    
    roles_query = select(Rol.nombre).join(RolUsuario, RolUsuario.id_rol == Rol.id).where(RolUsuario.id_usuario == usuario.id)
    roles_result = await db.execute(roles_query)
    roles = [r[0] for r in roles_result.all()]
    
    nombres_parts = [p for p in (persona.nombre, persona.apellido_p, persona.apellido_m) if p] if persona else []
    nombre_completo = " ".join(nombres_parts) if nombres_parts else "Sin nombre"
    
    return UsuarioAdminResponse(
        id=usuario.id,
        username=usuario.nombre,
        email=persona.email if persona else "Sin email",
        nombre_completo=nombre_completo,
        ci=persona.ci if persona else None,
        roles=roles,
        is_active=usuario.is_active
    )
