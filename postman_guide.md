# Guía Completa de Pruebas en Postman

Esta guía describe los flujos completos para probar tu backend en Postman. La URL base asumida es `http://localhost:8000/api/v1`. 

Recuerda que para los endpoints protegidos, debes enviar el token JWT en la cabecera (Header):
`Authorization: Bearer <tu_token_aqui>`

---

## 1. Flujo de Autenticación y Usuarios

### 1.1 Web (Administradores y Dueños de Taller)
- **Iniciar Registro (Enviar OTP):** `POST /auth/web/register/init`
  - Body: `{"email": "taller@ejemplo.com", "password": "mipassword", "nombre": "Juan", "apellido": "Perez", "telefono": "12345678"}`
- **Completar Registro (Verificar OTP):** `POST /auth/web/register/complete`
  - Body: `{"email": "taller@ejemplo.com", "code": "123456"}` *(Retorna Token JWT)*
- **Login Web:** `POST /auth/web/login`
  - Body: `{"email": "taller@ejemplo.com", "password": "mipassword"}` *(Retorna Token JWT)*

### 1.2 Móvil (Clientes / Conductores)
- **Revisar si el email existe:** `POST /auth/mobile/check-email`
  - Body: `{"email": "cliente@ejemplo.com"}`
- **Registrar (Pide OTP al correo):** `POST /auth/mobile/register`
  - Body: `{"email": "cliente@ejemplo.com"}`
- **Verificar OTP:** `POST /auth/mobile/verify-otp`
  - Body: `{"email": "cliente@ejemplo.com", "code": "123456"}` *(Retorna Token JWT)*

---

## 2. Flujo de Gestión de Taller (Requiere Login Web/Admin)

- **Solicitar Afiliación de Taller:** `POST /solicitudes/afiliacion/`
  - Permite a un dueño de taller solicitar el registro de su negocio.
- **Crear Empleado:** `POST /empleados/`
  - Body: Datos del empleado (nombre, email, rol).
- **Crear Técnico:** `POST /tecnicos/`
  - Body: Asignar un rol de técnico a un usuario/empleado.
- **Registrar Vehículo del Taller (Grúa, Moto, etc.):** `POST /vehiculos_taller/`
  - Body: `{"matricula": "ABC-123", "marca": "Toyota", "tipo": "grua", "id_taller": 1}`

---

## 3. Flujo Core del Cliente (Requiere Login Móvil/Cliente)

- **Registrar Vehículo del Cliente:** `POST /vehiculos/`
  - Body: `{"matricula": "XYZ-987", "marca": "Ford", "modelo": "Fiesta", "anio": 2020}`
- **Solicitar Diagnóstico (Con IA / Evidencias):** `POST /diagnosticos/multiple-files` (Form-Data)
  - Aquí el cliente sube fotos, audios o texto para que la IA diagnostique el problema.
  - Form-data: `id_vehiculo`, `latitud`, `longitud`, `archivos (files)`.
- **Solicitar Servicio a Talleres:** `POST /servicios/{diagnostico_id}/solicitar-taller`
  - El cliente elige enviar su diagnóstico a un taller o hacer una búsqueda (broadcast).

---

## 4. Flujo de Atención del Taller y Técnico

- **Taller Acepta la Solicitud:** `POST /taller/servicios/solicitudes/{solicitud_id}/aceptar`
  - El administrador del taller acepta ir a ayudar al cliente (y puede asignar qué técnico y vehículo irá).
- **Técnico Actualiza Estado:** `POST /tecnico/servicios/servicios/{servicio_id}/actualizar-estado`
  - Body: `{"estado": "en_camino"}` (luego `en_lugar`, `en_atencion`).
- **Monitoreo (Cliente o Taller):** `GET /monitoreo/servicio/{servicio_id}`
  - Muestra el ETA, la ruta y el estado actual del servicio.

---

## 5. Comunicación y Pagos

- **Enviar Mensaje de Chat:** `POST /mensajes/servicio/{servicio_id}`
  - Body: `{"texto": "Ya estoy llegando a tu ubicación."}`
- **Listar Mensajes:** `GET /mensajes/servicio/{servicio_id}`
- **Generar Cobro (Técnico):** `POST /pagos/servicio/{servicio_id}/generar`
  - Body: `{"monto_total": 50.00}` *(Genera enlace de pago Stripe o QR)*
- **Pago en Efectivo (Técnico):** `POST /pagos/servicio/{servicio_id}/pago-efectivo`
  - Body: `{"monto_total": 50.00}` *(Marca el servicio como pagado y finalizado)*
- **Valorar Servicio (Cliente):** `POST /cliente/servicios/servicio/{servicio_id}/valorar`
  - Body: `{"puntos": 5, "comentario": "Excelente servicio, muy rápido."}`

---

## Consejos para Postman
1. **Usa Variables de Entorno:** Crea variables como `{{base_url}}` y `{{token_cliente}}`, `{{token_taller}}` para no tener que copiar y pegar los tokens manualmente en cada petición.
2. **Pre-request Scripts:** Puedes usar un script en Postman en el endpoint de Login para que guarde automáticamente el token recibido en la variable de entorno:
   ```javascript
   var jsonData = pm.response.json();
   pm.environment.set("token_cliente", jsonData.access_token);
   ```
