from fastapi import APIRouter, Depends, UploadFile, File, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.perfil import UpdatePerfilRequest, PerfilResponse, RequestPasswordChangeRequest, ChangePasswordRequest, CreateUsuarioRequest
from app.services import profile_service
from app.core.deps import get_current_persona
from app.models.persona import Persona
from app.crud import usuario as crud_usuario

router = APIRouter(tags=["Perfil"])

@router.get("/me", response_model=PerfilResponse)
async def get_my_profile(
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """Obtiene el perfil completo del usuario autenticado."""
    from sqlalchemy import select
    from app.models.rol_usuario import RolUsuario
    from app.models.rol import Rol
    
    usuario = await crud_usuario.get_by_id_persona(db, current_persona.id)
    
    # Obtener TODOS los roles del usuario
    roles = []
    if usuario:
        result = await db.execute(
            select(Rol.nombre)
            .join(RolUsuario, RolUsuario.id_rol == Rol.id)
            .where(RolUsuario.id_usuario == usuario.id)
        )
        roles = [row[0] for row in result.all()]
    
    return PerfilResponse(
        id_usuario=usuario.id if usuario else None,
        email=current_persona.email,
        username=usuario.nombre if usuario else None,
        url_img_perfil=usuario.url_img_perfil if usuario else None,
        nombre=current_persona.nombre,
        apellido_p=current_persona.apellido_p,
        apellido_m=current_persona.apellido_m,
        ci=current_persona.ci,
        complemento=current_persona.complemento,
        telefono=current_persona.telefono,
        direccion=current_persona.direccion,
        roles=roles,  # Enviar lista de roles
        tenant_id=usuario.tenant_id if usuario else None,
    )

@router.put("/me", response_model=PerfilResponse)
async def update_my_profile(
    req: UpdatePerfilRequest,
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """Actualiza el perfil (datos personales, nombre de usuario, foto)."""
    from sqlalchemy import select
    from app.models.rol_usuario import RolUsuario
    from app.models.rol import Rol
    
    # Datos de persona (excluyendo username y url_img_perfil)
    persona_update = req.dict(exclude={"username", "url_img_perfil"})
    # Llamar al servicio
    result = await profile_service.update_profile(
        db=db,
        persona_id=current_persona.id,
        data=persona_update,
        username=req.username,
        url_img_perfil=req.url_img_perfil
    )
    persona = result["persona"]
    usuario = result["usuario"]
    
    # Obtener TODOS los roles del usuario
    roles = []
    if usuario:
        result_rol = await db.execute(
            select(Rol.nombre)
            .join(RolUsuario, RolUsuario.id_rol == Rol.id)
            .where(RolUsuario.id_usuario == usuario.id)
        )
        roles = [row[0] for row in result_rol.all()]
    
    return PerfilResponse(
        id_usuario=usuario.id if usuario else None,
        email=persona.email,
        username=usuario.nombre if usuario else None,
        url_img_perfil=usuario.url_img_perfil if usuario else None,
        nombre=persona.nombre,
        apellido_p=persona.apellido_p,
        apellido_m=persona.apellido_m,
        ci=persona.ci,
        complemento=persona.complemento,
        telefono=persona.telefono,
        direccion=persona.direccion,
        roles=roles,
        tenant_id=usuario.tenant_id if usuario else None,
    )

@router.post("/create-usuario", response_model=PerfilResponse, status_code=status.HTTP_201_CREATED)
async def create_usuario(
    req: CreateUsuarioRequest,
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """Crea un usuario (username + password) para la persona autenticada."""
    from sqlalchemy import select
    from app.models.rol_usuario import RolUsuario
    from app.models.rol import Rol
    
    result = await profile_service.create_usuario(
        db=db,
        persona_id=current_persona.id,
        username=req.username,
        password=req.password
    )
    persona = result["persona"]
    usuario = result["usuario"]
    
    # Obtener TODOS los roles del usuario
    roles = []
    if usuario:
        result_rol = await db.execute(
            select(Rol.nombre)
            .join(RolUsuario, RolUsuario.id_rol == Rol.id)
            .where(RolUsuario.id_usuario == usuario.id)
        )
        roles = [row[0] for row in result_rol.all()]
    
    return PerfilResponse(
        id_usuario=usuario.id if usuario else None,
        email=persona.email,
        username=usuario.nombre if usuario else None,
        url_img_perfil=usuario.url_img_perfil if usuario else None,
        nombre=persona.nombre,
        apellido_p=persona.apellido_p,
        apellido_m=persona.apellido_m,
        ci=persona.ci,
        complemento=persona.complemento,
        telefono=persona.telefono,
        direccion=persona.direccion,
        roles=roles,
        tenant_id=usuario.tenant_id if usuario else None,
    )

@router.post("/upload-photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """Sube una nueva foto de perfil."""
    photo_url = await profile_service.upload_profile_picture(db, current_persona.id, file)
    return {"photo_url": photo_url}

@router.delete("/photo", status_code=204)
async def delete_profile_photo(
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """Elimina la foto de perfil del usuario."""
    await profile_service.delete_profile_picture(db, current_persona.id)
    return Response(status_code=204)

@router.post("/request-password-change")
async def request_password_change(
    req: RequestPasswordChangeRequest,
    db: AsyncSession = Depends(get_db)
):
    await profile_service.request_password_change_otp(db, req.email)
    return {"message": "Código enviado a tu correo"}

@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Cambia la contraseña usando OTP."""
    await profile_service.change_password(db, req.email, req.code, req.new_password)
    return {"message": "Contraseña actualizada correctamente"}