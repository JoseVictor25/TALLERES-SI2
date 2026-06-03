import secrets
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
from app.core.constants import OTP_EXPIRE_MINUTES
from app.core.exceptions import OTPNotFoundError, OTPExpiredError, OTPSendError

# Almacenamiento en memoria: email -> {"code": str, "expires_at": datetime, "temp_data": dict}
_otp_storage: Dict[str, dict] = {}

def generate_otp() -> str:
    """Genera un código OTP de 6 dígitos criptográficamente seguro."""
    return f"{secrets.randbelow(1_000_000):06d}"

def store_otp(
    email: str,
    otp: str,
    temp_data: Optional[dict] = None
) -> None:
    """
    Almacena un OTP con su fecha de expiración y datos temporales asociados.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    _otp_storage[email] = {
        "code": otp,
        "expires_at": expires_at,
        "temp_data": temp_data or {}
    }

def get_otp_data(email: str) -> Optional[dict]:
    """
    Recupera los datos del OTP sin eliminarlos.
    Si el OTP ha expirado, lo elimina y retorna None.
    """
    record = _otp_storage.get(email)
    if not record:
        raise OTPNotFoundError()
    if datetime.now(timezone.utc) > record["expires_at"]:
        delete_otp(email)
        raise OTPExpiredError()
    return record

def delete_otp(email: str) -> None:
    """Elimina el OTP del almacenamiento."""
    _otp_storage.pop(email, None)

def _send_otp_email_sync(email: str, otp: str) -> None:
    """
    Envía el OTP por correo electrónico usando SMTP.
    """
    subject = "Tu código de verificación"
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Código de verificación</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #E6E8E5; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 20px auto; background-color: #FFFFFF; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <tr>
                <td style="padding: 30px 30px 20px 30px; text-align: center; background-color: #932D30; border-radius: 16px 16px 0 0;">
                    <h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">SmartAssist</h1>
                    <p style="margin: 5px 0 0 0; color: #F5F2EB; font-size: 14px;">Plataforma de Asistencia Vehicular</p>
                </td>
            </tr>
            <tr>
                <td style="padding: 30px;">
                    <h2 style="color: #421413; margin-top: 0;">Hola,</h2>
                    <p style="color: #2C2C2C; font-size: 16px; line-height: 1.5;">Has solicitado un código de verificación. Tu código es:</p>
                    <div style="background-color: #E6E8E5; border-radius: 12px; padding: 15px; text-align: center; margin: 20px 0;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 4px; color: #932D30;">{otp}</span>
                    </div>
                    <p style="color: #2C2C2C; font-size: 16px; line-height: 1.5;">Este código expira en <strong>{OTP_EXPIRE_MINUTES} minutos</strong>.</p>
                    <p style="color: #2C2C2C; font-size: 16px; line-height: 1.5;">Si no solicitaste este código, ignora este mensaje.</p>
                    <hr style="border: none; border-top: 1px solid #B76369; margin: 30px 0;">
                    <p style="color: #52341A; font-size: 12px; text-align: center;">© 2025 SmartAssist. Todos los derechos reservados.</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    # Crear mensaje con nombre personalizado en el remitente
    msg = MIMEMultipart()
    msg["From"] = f"SmartAssist <{settings.SMTP_FROM}>"
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        # Conectar al servidor SMTP
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()  # Habilitar TLS
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        raise OTPSendError(f"No se pudo enviar el email a {email}: {str(e)}")

async def send_otp_email_safe(
    email: str,
    action: str,
    extra_temp_data: Optional[dict] = None
) -> str:
    """
    Genera un OTP, lo envía por email (de forma asíncrona) y lo guarda en memoria.
    """
    otp = generate_otp()
    temp_data = {"action": action}
    if extra_temp_data:
        temp_data.update(extra_temp_data)
    store_otp(email, otp, temp_data=temp_data)

    # Enviar email en un hilo separado para no bloquear
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _send_otp_email_sync, email, otp)

    return otp