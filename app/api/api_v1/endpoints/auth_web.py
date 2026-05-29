from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, RegisterInitRequest, RegisterCompleteRequest
from app.services import auth_service, registration_service
from app.services.bitacora_service import registrar_acceso
from app.models.bitacora_acceso import AccionAcceso
from app.core.exceptions import InvalidTokenError

router = APIRouter(tags=["Authentication - Web"])

@router.post("/login", response_model=TokenResponse)
async def web_login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        token_response = await auth_service.login_user(db, req.email, req.password)
        
        # Obtener el usuario decodificando temporalmente o buscando en base de datos.
        # En auth_service.login_user se valida. Necesitaría el ID del usuario.
        # auth_service.login_user() ya fue exitoso aquí.
        # Como es complicado sacar el ID sin duplicar código, lo guardaré sin ID pero indicando email y exito
        await registrar_acceso(db, AccionAcceso.LOGIN_EXITOSO, request, email_intentado=req.email, exito=True)
        return token_response
    except HTTPException as e:
        await registrar_acceso(db, AccionAcceso.LOGIN_FALLIDO, request, email_intentado=req.email, exito=False)
        raise e

@router.post("/logout", status_code=204)
async def web_logout(request: Request, db: AsyncSession = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise InvalidTokenError()
    token = auth_header.split(" ")[1]
    
    await registrar_acceso(db, AccionAcceso.LOGOUT, request, exito=True)
    await auth_service.logout_user(db, token)
    return Response(status_code=204)

@router.post("/register/init")
async def register_init(req: RegisterInitRequest, db: AsyncSession = Depends(get_db)):
    await registration_service.start_web_registration(db, req.dict())
    return {"message": "OTP sent"}

@router.post("/register/complete", response_model=TokenResponse)
async def register_complete(req: RegisterCompleteRequest, db: AsyncSession = Depends(get_db)):
    return await registration_service.complete_web_registration(db, req.email, req.code)