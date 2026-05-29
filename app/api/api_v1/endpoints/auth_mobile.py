from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.auth import (
    EmailCheckRequest, EmailCheckResponse,
    RequestOTPRequest, VerifyOTPRequest,
    LoginRequest, TokenResponse
)
from app.crud import persona as crud_persona, usuario as crud_usuario
from app.services import auth_service, registration_service
from app.services.otp_service import get_otp_data
from app.services.bitacora_service import registrar_acceso
from app.models.bitacora_acceso import AccionAcceso
from app.core.exceptions import InvalidOTPFlowError, InvalidTokenError

router = APIRouter(tags=["Authentication - Mobile"])

@router.post("/check-email", response_model=EmailCheckResponse)
async def check_email(req: EmailCheckRequest, db: AsyncSession = Depends(get_db)):
    persona = await crud_persona.get_by_email(db, req.email)
    if not persona:
        return EmailCheckResponse(exists=False, has_user=False)
    usuario = await crud_usuario.get_by_id_persona(db, persona.id)
    return EmailCheckResponse(exists=True, has_user=usuario is not None)

@router.post("/request-otp")
async def request_otp(req: RequestOTPRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.start_conductor_login(db, req.email)
    return {"message": "OTP sent"}

@router.post("/register")
async def register_new_conductor(req: RequestOTPRequest, db: AsyncSession = Depends(get_db)):
    await registration_service.start_conductor_registration(db, req.email)
    return {"message": "OTP sent. Please verify to complete registration."}

@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(request: Request, req: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    try:
        record = get_otp_data(req.email)
        action = record["temp_data"].get("action")
        if action == "register":
            resp = await registration_service.complete_conductor_registration(db, req.email, req.code, req.fcm_token)
            await registrar_acceso(db, AccionAcceso.LOGIN_EXITOSO, request, email_intentado=req.email, exito=True)
            return resp
        elif action == "verify":
            resp = await auth_service.complete_conductor_login(db, req.email, req.code, req.fcm_token)
            await registrar_acceso(db, AccionAcceso.LOGIN_EXITOSO, request, email_intentado=req.email, exito=True)
            return resp
        else:
            raise InvalidOTPFlowError()
    except HTTPException as e:
        await registrar_acceso(db, AccionAcceso.LOGIN_FALLIDO, request, email_intentado=req.email, exito=False)
        raise e

@router.post("/login", response_model=TokenResponse)
async def login_with_password(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        resp = await auth_service.login_user(db, req.email, req.password, req.fcm_token)
        await registrar_acceso(db, AccionAcceso.LOGIN_EXITOSO, request, email_intentado=req.email, exito=True)
        return resp
    except HTTPException as e:
        await registrar_acceso(db, AccionAcceso.LOGIN_FALLIDO, request, email_intentado=req.email, exito=False)
        raise e

@router.post("/logout", status_code=204)
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise InvalidTokenError()
    token = auth_header.split(" ")[1]
    
    await registrar_acceso(db, AccionAcceso.LOGOUT, request, exito=True)
    await auth_service.logout_user(db, token)
    return Response(status_code=204)