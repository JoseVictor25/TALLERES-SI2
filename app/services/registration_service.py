import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import (
    persona as crud_persona, 
    usuario as crud_usuario, 
    rol as crud_rol, 
    rol_usuario as crud_rol_usuario
)
from .user_service import (
    create_persona, 
    create_usuario_from_persona,
    update_persona_data
)
from .otp_service import send_otp_email_safe, get_otp_data, delete_otp
from .session_service import create_token_and_session
from app.core.constants import ROL_CLIENTE
from app.schemas.auth import TokenResponse
from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidOTPError,
    InvalidOTPFlowError,
    UsernameTakenError,
    CIDuplicatedError,
    PersonaNotFoundError,
    RoleNotFoundError,
)

logger = logging.getLogger(__name__)

async def start_conductor_registration(db: AsyncSession, email: str) -> None:
    """
    Inicia el registro de un nuevo conductor (solo email). Envía OTP.
    No registra a la persona aún.
    """
    existing = await crud_persona.get_by_email(db, email)
    if existing:
        raise EmailAlreadyRegisteredError()
    await send_otp_email_safe(email, action="register")
    logger.info(f"Registro iniciado para {email}")

async def complete_conductor_registration(db: AsyncSession, email: str, code: str, fcm_token: str = None) -> TokenResponse:
    """
    Completa el registro de conductor: verifica OTP, crea persona y devuelve token.
    """
    record = get_otp_data(email)
    if not record or record["code"] != code:
        raise InvalidOTPError()
    if record["temp_data"].get("action") != "register":
        raise InvalidOTPFlowError()

    # Crear persona (solo email)
    persona = await create_persona(db, email)
    await db.commit()
    delete_otp(email)
    access_token = await create_token_and_session(db, email, fcm_token)
    await db.commit()
    logger.info(f"Nuevo conductor registrado: {email}")
    return TokenResponse(access_token=access_token)

async def start_web_registration(db: AsyncSession, data: dict) -> None:
    """
    Inicia registro web: valida email, username, CI y envía OTP con los datos temporales.
    """
    email = data["email"]
    username = data["username"]
    # Verificar email
    existing_persona = await crud_persona.get_by_email(db, email)
    if existing_persona:
        usuario = await crud_usuario.get_by_id_persona(db, existing_persona.id)
        if usuario:
            raise EmailAlreadyRegisteredError()
    # Verificar username único
    existing_user = await crud_usuario.get_by_nombre(db, username)
    if existing_user:
        raise UsernameTakenError()
    # Verificar CI único si se proporciona
    if data.get("ci"):
        existing_ci = await crud_persona.get_by_ci_complemento(db, data["ci"], data.get("complemento"))
        if existing_ci:
            raise CIDuplicatedError()
    # Guardar datos temporales
    temp_data = {
        "data": data,
        "persona_exists": existing_persona is not None,
        "id_persona": existing_persona.id if existing_persona else None
    }
    await send_otp_email_safe(email, action="register", extra_temp_data=temp_data)

async def complete_web_registration(db: AsyncSession, email: str, code: str) -> TokenResponse:
    """
    Completa registro web: verifica OTP, crea/actualiza persona y usuario, asigna rol cliente.
    """
    record = get_otp_data(email)
    if not record or record["code"] != code:
        raise InvalidOTPError()
    temp_data = record["temp_data"]
    if temp_data.get("action") != "register":
        raise InvalidOTPFlowError()

    user_data = temp_data["data"]
    persona_exists = temp_data.get("persona_exists", False)
    id_persona = temp_data.get("id_persona")

    # Datos personales proporcionados (sin email, username, password)
    persona_extra = {k: v for k, v in user_data.items() if k not in ["email", "username", "password"]}

    # No usar db.begin() aquí porque la transacción ya está activa
    if persona_exists and id_persona:
        # Recuperar persona existente
        persona = await crud_persona.get(db, id_persona)
        if not persona:
            raise PersonaNotFoundError()
        # Actualizar persona con los datos opcionales (solo si hay datos)
        if persona_extra:
            persona = await update_persona_data(db, persona, persona_extra)
    else:
        # Crear nueva persona con los datos opcionales
        persona = await create_persona(db, user_data["email"], persona_extra)

    # Crear usuario
    nuevo_usuario = await create_usuario_from_persona(db, persona, user_data["username"], user_data["password"])

    # Asignar rol 'cliente'
    rol = await crud_rol.get_by_nombre(db, ROL_CLIENTE)
    if not rol:
        raise RoleNotFoundError(ROL_CLIENTE)
    await crud_rol_usuario.add_rol(db, nuevo_usuario.id, rol.id)

    await db.commit()
    delete_otp(email)
    access_token = await create_token_and_session(db, user_data["email"])
    await db.commit()
    logger.info(f"Nuevo usuario web registrado: {user_data['email']}")
    return TokenResponse(access_token=access_token)

async def direct_web_registration(db: AsyncSession, data: dict) -> TokenResponse:
    """
    Registro web directo sin verificación OTP (usado para flujo de Taller).
    """
    email = data["email"]
    username = data.get("username", email.split('@')[0])
    
    # Verificar email
    existing_persona = await crud_persona.get_by_email(db, email)
    if existing_persona:
        usuario = await crud_usuario.get_by_id_persona(db, existing_persona.id)
        if usuario:
            raise EmailAlreadyRegisteredError()
            
    # Verificar username
    existing_user = await crud_usuario.get_by_nombre(db, username)
    if existing_user:
        raise UsernameTakenError()

    persona_extra = {k: v for k, v in data.items() if k not in ["email", "username", "password", "taller_name"]}

    if existing_persona:
        persona = existing_persona
        if persona_extra:
            persona = await update_persona_data(db, persona, persona_extra)
    else:
        persona = await create_persona(db, email, persona_extra)

    # Crear usuario
    nuevo_usuario = await create_usuario_from_persona(db, persona, username, data["password"])

    # Asignar rol 'cliente' por defecto (luego al pagar se le da Administrador de Taller)
    rol = await crud_rol.get_by_nombre(db, ROL_CLIENTE)
    if not rol:
        from app.models.rol import Rol
        rol = Rol(nombre=ROL_CLIENTE, descripcion="Rol de cliente creado automáticamente")
        db.add(rol)
        await db.commit()
        await db.refresh(rol)

    await crud_rol_usuario.add_rol(db, nuevo_usuario.id, rol.id)

    await db.commit()
    access_token = await create_token_and_session(db, email)
    await db.commit()
    logger.info(f"Nuevo Taller Admin web registrado directamente: {email}")
    return TokenResponse(access_token=access_token)