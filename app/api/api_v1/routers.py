# app/api/api_v1/routers.py
from fastapi import APIRouter
from .endpoints import (
    auth_mobile,
    auth_web,
    perfiles,
    vehiculos,
    solicitudes,
    diagnosticos,
    servicios,
    talleres,
    empleados,
    tecnicos,
    especialidades,
    admin_categorias,
    admin_tipos,
    vehiculos_taller,
    admin_configuracion,
    taller_servicios,
    tecnico_servicios,
    cliente_servicios,
    monitoreo,
    mensajes,
    pagos,
    admin_usuarios,
    notifications,
    admin_bitacora,
    tenants
)
from .endpoints import websockets as ws_endpoints

api_router = APIRouter()

api_router.include_router(auth_mobile.router, prefix="/auth/mobile", tags=["Authentication - Mobile"])
api_router.include_router(auth_web.router, prefix="/auth/web", tags=["Authentication - Web"])
api_router.include_router(perfiles.router, prefix="/perfil", tags=["Perfil"])
api_router.include_router(vehiculos.router, prefix="/vehiculos", tags=["Vehículos"])
api_router.include_router(solicitudes.router, prefix="/solicitudes/afiliacion", tags=["Afiliación de Talleres"])
api_router.include_router(diagnosticos.router, tags=["Diagnósticos"])
api_router.include_router(servicios.router, tags=["Servicios"])
api_router.include_router(talleres.router, prefix="/talleres", tags=["Talleres"])
api_router.include_router(empleados.router, tags=["Empleados"])
api_router.include_router(tecnicos.router, tags=["Técnicos"])
api_router.include_router(especialidades.router, tags=["Especialidades"])
api_router.include_router(admin_categorias.router, prefix="/admin/categorias", tags=["Admin - Categorías Incidente"])
api_router.include_router(admin_tipos.router, prefix="/admin/tipos", tags=["Admin - Tipos Incidente"])
api_router.include_router(vehiculos_taller.router, tags=["Vehículos Taller"])
api_router.include_router(admin_configuracion.router, prefix="/admin/configuracion", tags=["Admin - Configuración"])
api_router.include_router(admin_usuarios.router, prefix="/admin/usuarios", tags=["Admin - Usuarios"])
api_router.include_router(admin_bitacora.router, prefix="/admin/sistema/bitacora", tags=["Admin - Bitácora"])
api_router.include_router(taller_servicios.router, tags=["Taller - Gestión de Servicios"])
api_router.include_router(tecnico_servicios.router, tags=["Técnico - Servicios Móvil"])
api_router.include_router(cliente_servicios.router, tags=["Cliente - Seguimiento de Servicios"])
api_router.include_router(monitoreo.router)
api_router.include_router(mensajes.router)
api_router.include_router(pagos.router)
api_router.include_router(notifications.router)
api_router.include_router(tenants.router)
api_router.include_router(ws_endpoints.router)