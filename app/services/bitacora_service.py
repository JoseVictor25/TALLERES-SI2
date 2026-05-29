import logging
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
from typing import Optional

from app.models.bitacora_acceso import BitacoraAcceso, AccionAcceso
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def registrar_acceso(
    db: AsyncSession, # Se mantiene para compatibilidad de firma pero creamos una nueva
    accion: AccionAcceso,
    request: Request,
    id_usuario: Optional[int] = None,
    email_intentado: Optional[str] = None,
    exito: bool = False
):
    try:
        ip_address = request.client.host if request.client else None
        
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip_address = forwarded_for.split(',')[0].strip()

        user_agent = request.headers.get("user-agent")

        bitacora = BitacoraAcceso(
            id_usuario=id_usuario,
            email_intentado=email_intentado,
            ip_address=ip_address,
            user_agent=user_agent,
            accion=accion,
            exito=exito
        )

        async with AsyncSessionLocal() as new_session:
            new_session.add(bitacora)
            await new_session.commit()
    except Exception as e:
        logger.error(f"Error registrando bitacora de acceso: {e}")
        pass
