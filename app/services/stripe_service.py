import stripe
from app.core.config import settings

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

def crear_sesion_checkout(
    servicio_id: int, 
    monto_total: float, 
    descripcion: str = "Servicio de Asistencia Vial"
) -> dict:
    """
    Crea una sesión de Stripe Checkout y devuelve el ID y la URL.
    """
    if not settings.STRIPE_SECRET_KEY or "tu_llave_secreta" in settings.STRIPE_SECRET_KEY:
        # Modo simulación si no hay llave real
        return {
            "id": f"sim_session_{servicio_id}",
            "url": f"https://sandbox.stripe.com/pay/sim_{servicio_id}"
        }

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'bob', # O la moneda local
                    'product_data': {
                        'name': descripcion,
                    },
                    # Stripe usa centavos, así que multiplicamos por 100
                    'unit_amount': int(monto_total * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            # Redirecciones (el backend servirá una página HTML simple para estas rutas)
            success_url=f"{settings.BASE_URL}/api/v1/pagos/exito?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.BASE_URL}/api/v1/pagos/cancelado",
            metadata={
                "servicio_id": str(servicio_id)
            }
        )
        return {
            "id": session.id,
            "url": session.url
        }
    except Exception as e:
        raise ValueError(f"Error al conectar con Stripe: {str(e)}")

def verificar_webhook(payload: bytes, signature: str) -> dict:
    """
    Verifica la firma del webhook recibido de Stripe y devuelve el evento.
    """
    if not settings.STRIPE_WEBHOOK_SECRET or "tu_secreto" in settings.STRIPE_WEBHOOK_SECRET:
        # Modo simulación
        import json
        return json.loads(payload.decode('utf-8'))

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET
        )
        return event
    except stripe.error.SignatureVerificationError as e:
        raise ValueError("Firma de Stripe inválida")
    except ValueError as e:
        raise ValueError("Carga útil de Stripe inválida")
