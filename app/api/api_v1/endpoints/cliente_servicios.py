"""
Endpoints para clientes móvil - Seguimiento de servicios
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.deps import get_current_usuario
from app.models.usuario import Usuario
from app.models.servicio import Servicio, EstadoServicio
from app.models.servicio_tecnico import ServicioTecnico
from app.models.solicitud_servicio import SolicitudServicio
from app.models.solicitud_diagnostico import SolicitudDiagnostico
from app.models.diagnostico import Diagnostico
from app.models.taller import Taller
from app.models.empleado import Empleado
from app.models.historial_estado_servicio import HistorialEstadoServicio
from app.crud import empleado as empleado_crud
from app.crud import crud_empleado_ubicacion
from app.schemas.servicio import (
    ServicioSeguimientoClienteResponse,
    TallerInfoResponse,
    TecnicoUbicacionResponse,
    EstadoHistorialClienteResponse
)
from app.schemas.valoracion import ValoracionCreate, ValoracionResponse
from app.crud import crud_valoracion
from app.services import valoracion_service, servicio_service
from app.schemas.servicio import SolicitudServicioListResponse
from geoalchemy2.shape import to_shape
from datetime import datetime

router = APIRouter(prefix="/cliente", tags=["Cliente - Seguimiento de Servicios"])


def get_estado_descripcion(estado: str) -> str:
    """Retorna la descripción en español del estado"""
    map_estados = {
        'creado': 'Creado',
        'tecnico_asignado': 'Técnico Asignado',
        'en_camino': 'En Camino',
        'en_lugar': 'En el Lugar',
        'en_atencion': 'En Atención',
        'finalizado': 'Finalizado',
        'cancelado': 'Cancelado'
    }
    return map_estados.get(estado, estado)


@router.post("/solicitudes/{solicitud_id}/aceptar-cotizacion", status_code=status.HTTP_200_OK)
async def aceptar_cotizacion(
    solicitud_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    El cliente acepta la cotización de un taller.
    """
    try:
        solicitud = await servicio_service.aceptar_cotizacion_cliente(
            db=db,
            id_solicitud=solicitud_id,
            id_persona_cliente=current_usuario.id_persona
        )
        return {"message": "Cotización aceptada", "estado": solicitud.estado.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/solicitudes/{solicitud_id}/rechazar-cotizacion", status_code=status.HTTP_200_OK)
async def rechazar_cotizacion(
    solicitud_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    El cliente rechaza la cotización de un taller.
    """
    try:
        solicitud = await servicio_service.rechazar_cotizacion_cliente(
            db=db,
            id_solicitud=solicitud_id,
            id_persona_cliente=current_usuario.id_persona
        )
        return {"message": "Cotización rechazada", "estado": solicitud.estado.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/servicios/{servicio_id}/cancelar", status_code=status.HTTP_200_OK)
async def cancelar_servicio(
    servicio_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    El cliente cancela un servicio en curso, liberando los recursos del taller.
    """
    try:
        servicio = await servicio_service.cancelar_servicio_cliente(
            db=db,
            id_servicio=servicio_id,
            id_persona_cliente=current_usuario.id_persona
        )
        return {"message": "Servicio cancelado", "estado": servicio.estado.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/servicio-actual", response_model=Optional[ServicioSeguimientoClienteResponse])
async def obtener_servicio_actual(
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el servicio actual en proceso del cliente con seguimiento completo:
    - Historial de estados
    - Ubicación de técnicos
    - Información del taller
    """
    # Buscar servicio activo del cliente
    # El cliente tiene servicios a través de solicitudes de diagnóstico
    result = await db.execute(
        select(Servicio).join(
            SolicitudServicio, Servicio.id_solicitud_servicio == SolicitudServicio.id
        ).join(
            Diagnostico, SolicitudServicio.id_diagnostico == Diagnostico.id
        ).join(
            SolicitudDiagnostico, Diagnostico.id_solicitud_diagnostico == SolicitudDiagnostico.id
        ).where(
            and_(
                SolicitudDiagnostico.id_persona == current_usuario.id_persona,
                Servicio.estado.in_([
                    EstadoServicio.creado,
                    EstadoServicio.tecnico_asignado,
                    EstadoServicio.en_camino,
                    EstadoServicio.en_lugar,
                    EstadoServicio.en_atencion
                ])
            )
        ).options(
            selectinload(Servicio.taller),
            selectinload(Servicio.solicitud_servicio).selectinload(SolicitudServicio.diagnostico)
        ).order_by(Servicio.fecha.desc())
    )
    
    servicio = result.scalar_one_or_none()
    
    if not servicio:
        return None
    
    # Obtener información del taller
    taller = servicio.taller
    taller_ubicacion = None
    if taller.ubicacion:
        point = to_shape(taller.ubicacion)
        taller_ubicacion = f"{point.y},{point.x}"
    
    taller_info = TallerInfoResponse(
        id=taller.id,
        nombre=taller.nombre,
        telefono=taller.telefono,
        email=taller.email,
        direccion=None,  # El modelo Taller no tiene dirección
        ubicacion=taller_ubicacion,
        puntos=float(taller.puntos) if taller.puntos else 0.0
    )
    
    # Obtener técnicos asignados con sus ubicaciones
    result_tecnicos = await db.execute(
        select(ServicioTecnico).where(
            ServicioTecnico.id_servicio == servicio.id
        )
    )
    asignaciones = result_tecnicos.scalars().all()
    
    tecnicos_response = []
    for asignacion in asignaciones:
        empleado = await empleado_crud.get_with_usuario(db, asignacion.id_empleado)
        if empleado:
            # Obtener ubicación activa del técnico
            ubicacion = await crud_empleado_ubicacion.empleado_ubicacion.get_ubicacion_activa(
                db, empleado.id
            )
            
            tecnicos_response.append(TecnicoUbicacionResponse(
                id_empleado=empleado.id,
                nombre_completo=empleado.usuario.nombre,
                latitud=float(ubicacion.latitud) if ubicacion else None,
                longitud=float(ubicacion.longitud) if ubicacion else None,
                timestamp=ubicacion.timestamp if ubicacion else None,
                tiene_ubicacion=ubicacion is not None
            ))
    
    
    # Obtener historial de estados
    result_historial = await db.execute(
        select(HistorialEstadoServicio).where(
            HistorialEstadoServicio.id_servicio == servicio.id
        ).order_by(HistorialEstadoServicio.tiempo.asc())
    )
    historial = result_historial.scalars().all()
    
    historial_response = [
        EstadoHistorialClienteResponse(
            estado=h.estado.value,
            estado_descripcion=get_estado_descripcion(h.estado.value),
            tiempo=h.tiempo
        )
        for h in historial
    ]
    
    # Obtener ubicación del cliente (de la solicitud de diagnóstico)
    ubicacion_cliente = None
    if servicio.solicitud_servicio and servicio.solicitud_servicio.diagnostico:
        result_sol_diag = await db.execute(
            select(SolicitudDiagnostico).where(
                SolicitudDiagnostico.id == servicio.solicitud_servicio.diagnostico.id_solicitud_diagnostico
            )
        )
        sol_diag = result_sol_diag.scalar_one_or_none()
        if sol_diag and sol_diag.ubicacion:
            point = to_shape(sol_diag.ubicacion)
            ubicacion_cliente = f"{point.y},{point.x}"
    
    # Obtener descripción del diagnóstico
    diagnostico_descripcion = None
    if servicio.solicitud_servicio and servicio.solicitud_servicio.diagnostico:
        diagnostico_descripcion = servicio.solicitud_servicio.diagnostico.descripcion
    
    return ServicioSeguimientoClienteResponse(
        id=servicio.id,
        fecha=servicio.fecha,
        estado=servicio.estado.value,
        estado_descripcion=get_estado_descripcion(servicio.estado.value),
        taller=taller_info,
        tecnicos=tecnicos_response,
        historial_estados=historial_response,
        ubicacion_cliente=ubicacion_cliente,
        diagnostico_descripcion=diagnostico_descripcion
    )


@router.get("/servicio/{servicio_id}/tecnico/{empleado_id}/ruta")
async def obtener_ruta_tecnico(
    servicio_id: int,
    empleado_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene la ruta optimizada desde la ubicación del técnico hasta el cliente.
    Usa OSRM para calcular la ruta.
    """
    # Verificar que el servicio pertenece al cliente
    result = await db.execute(
        select(Servicio).join(
            SolicitudServicio, Servicio.id_solicitud_servicio == SolicitudServicio.id
        ).join(
            Diagnostico, SolicitudServicio.id_diagnostico == Diagnostico.id
        ).join(
            SolicitudDiagnostico, Diagnostico.id_solicitud_diagnostico == SolicitudDiagnostico.id
        ).where(
            and_(
                Servicio.id == servicio_id,
                SolicitudDiagnostico.id_persona == current_usuario.id_persona
            )
        ).options(
            selectinload(Servicio.solicitud_servicio).selectinload(SolicitudServicio.diagnostico)
        )
    )
    
    servicio = result.scalar_one_or_none()
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    # Verificar que el técnico está asignado al servicio
    result_asignacion = await db.execute(
        select(ServicioTecnico).where(
            and_(
                ServicioTecnico.id_servicio == servicio_id,
                ServicioTecnico.id_empleado == empleado_id
            )
        )
    )
    asignacion = result_asignacion.scalar_one_or_none()
    if not asignacion:
        raise HTTPException(status_code=404, detail="Técnico no asignado a este servicio")
    
    # Obtener ubicación del técnico
    ubicacion_tecnico = await crud_empleado_ubicacion.empleado_ubicacion.get_ubicacion_activa(
        db, empleado_id
    )
    
    if not ubicacion_tecnico:
        raise HTTPException(
            status_code=404,
            detail="El técnico no tiene ubicación disponible"
        )
    
    # Obtener ubicación del cliente
    result_sol_diag = await db.execute(
        select(SolicitudDiagnostico).where(
            SolicitudDiagnostico.id == servicio.solicitud_servicio.diagnostico.id_solicitud_diagnostico
        )
    )
    sol_diag = result_sol_diag.scalar_one_or_none()
    
    if not sol_diag or not sol_diag.ubicacion:
        raise HTTPException(status_code=404, detail="Ubicación del cliente no disponible")
    
    point_cliente = to_shape(sol_diag.ubicacion)
    
    # Calcular ruta usando OSRM
    import httpx
    
    lon_tecnico = float(ubicacion_tecnico.longitud)
    lat_tecnico = float(ubicacion_tecnico.latitud)
    lon_cliente = point_cliente.x
    lat_cliente = point_cliente.y
    
    osrm_url = f"http://router.project-osrm.org/route/v1/driving/{lon_tecnico},{lat_tecnico};{lon_cliente},{lat_cliente}"
    params = {
        "overview": "full",
        "geometries": "geojson"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(osrm_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != "Ok":
                raise HTTPException(status_code=500, detail="No se pudo calcular la ruta")
            
            route = data["routes"][0]
            geometry = route["geometry"]["coordinates"]
            distance = route["distance"]  # en metros
            duration = route["duration"]  # en segundos
            
            return {
                "ruta": geometry,  # Lista de [lon, lat]
                "distancia_metros": distance,
                "duracion_segundos": duration,
                "ubicacion_tecnico": {
                    "latitud": lat_tecnico,
                    "longitud": lon_tecnico
                },
                "ubicacion_cliente": {
                    "latitud": lat_cliente,
                    "longitud": lon_cliente
                }
            }
    
    except httpx.HTTPError:
        # Si falla OSRM, retornar línea recta
        return {
            "ruta": [[lon_tecnico, lat_tecnico], [lon_cliente, lat_cliente]],
            "distancia_metros": None,
            "duracion_segundos": None,
            "ubicacion_tecnico": {
                "latitud": lat_tecnico,
                "longitud": lon_tecnico
            },
            "ubicacion_cliente": {
                "latitud": lat_cliente,
                "longitud": lon_cliente
            },
            "fallback": True
        }



# ============================================================
# ENDPOINTS PARA VALORACIONES
# ============================================================

@router.post("/servicio/{servicio_id}/valorar", response_model=ValoracionResponse, status_code=status.HTTP_201_CREATED)
async def valorar_servicio(
    servicio_id: int,
    valoracion_data: ValoracionCreate,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Permite al cliente valorar un servicio finalizado.
    Solo se puede valorar servicios finalizados y una sola vez por servicio.
    """
    # Verificar que el servicio existe y pertenece al cliente
    result = await db.execute(
        select(Servicio).join(
            SolicitudServicio, Servicio.id_solicitud_servicio == SolicitudServicio.id
        ).join(
            Diagnostico, SolicitudServicio.id_diagnostico == Diagnostico.id
        ).join(
            SolicitudDiagnostico, Diagnostico.id_solicitud_diagnostico == SolicitudDiagnostico.id
        ).where(
            and_(
                Servicio.id == servicio_id,
                SolicitudDiagnostico.id_persona == current_usuario.id_persona
            )
        )
    )
    
    servicio = result.scalar_one_or_none()
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    # Verificar que el servicio esté finalizado
    if servicio.estado != EstadoServicio.finalizado:
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden valorar servicios finalizados"
        )
    
    # Verificar que no exista ya una valoración
    valoracion_existente = await crud_valoracion.valoracion.get_by_servicio(db, servicio_id)
    if valoracion_existente:
        raise HTTPException(
            status_code=400,
            detail="Este servicio ya ha sido valorado. Puedes actualizar tu valoración."
        )
    
    # Crear la valoración
    try:
        valoracion = await valoracion_service.crear_valoracion_y_actualizar_taller(
            db=db,
            id_servicio=servicio_id,
            puntos=valoracion_data.puntos,
            comentario=valoracion_data.comentario
        )
        
        await db.commit()
        await db.refresh(valoracion)
        
        return valoracion
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear valoración: {str(e)}")


@router.get("/servicio/{servicio_id}/valoracion", response_model=Optional[ValoracionResponse])
async def obtener_valoracion_servicio(
    servicio_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene la valoración de un servicio si existe.
    """
    # Verificar que el servicio pertenece al cliente
    result = await db.execute(
        select(Servicio).join(
            SolicitudServicio, Servicio.id_solicitud_servicio == SolicitudServicio.id
        ).join(
            Diagnostico, SolicitudServicio.id_diagnostico == Diagnostico.id
        ).join(
            SolicitudDiagnostico, Diagnostico.id_solicitud_diagnostico == SolicitudDiagnostico.id
        ).where(
            and_(
                Servicio.id == servicio_id,
                SolicitudDiagnostico.id_persona == current_usuario.id_persona
            )
        )
    )
    
    servicio = result.scalar_one_or_none()
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    # Obtener valoración
    valoracion = await crud_valoracion.valoracion.get_by_servicio(db, servicio_id)
    return valoracion


@router.put("/servicio/{servicio_id}/valoracion", response_model=ValoracionResponse)
async def actualizar_valoracion_servicio(
    servicio_id: int,
    valoracion_data: ValoracionCreate,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza la valoración de un servicio.
    """
    # Verificar que el servicio pertenece al cliente
    result = await db.execute(
        select(Servicio).join(
            SolicitudServicio, Servicio.id_solicitud_servicio == SolicitudServicio.id
        ).join(
            Diagnostico, SolicitudServicio.id_diagnostico == Diagnostico.id
        ).join(
            SolicitudDiagnostico, Diagnostico.id_solicitud_diagnostico == SolicitudDiagnostico.id
        ).where(
            and_(
                Servicio.id == servicio_id,
                SolicitudDiagnostico.id_persona == current_usuario.id_persona
            )
        )
    )
    
    servicio = result.scalar_one_or_none()
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    # Obtener valoración existente
    valoracion = await crud_valoracion.valoracion.get_by_servicio(db, servicio_id)
    if not valoracion:
        raise HTTPException(
            status_code=404,
            detail="No existe una valoración para este servicio. Usa POST para crear una."
        )
    
    # Actualizar valoración
    try:
        valoracion = await valoracion_service.actualizar_valoracion_y_taller(
            db=db,
            valoracion=valoracion,
            nuevos_puntos=valoracion_data.puntos,
            nuevo_comentario=valoracion_data.comentario
        )
        
        await db.commit()
        await db.refresh(valoracion)
        
        return valoracion
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar valoración: {str(e)}")



@router.get("/taller/{taller_id}/estadisticas")
async def obtener_estadisticas_taller(
    taller_id: int,
    current_usuario: Usuario = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene estadísticas de valoraciones de un taller.
    Útil para mostrar al cliente antes de solicitar un servicio.
    """
    from sqlalchemy import func
    
    # Obtener el taller
    result_taller = await db.execute(
        select(Taller).where(Taller.id == taller_id)
    )
    taller = result_taller.scalar_one_or_none()
    
    if not taller:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    
    # Contar total de valoraciones
    result_count = await db.execute(
        select(func.count(Valoracion.id)).select_from(Valoracion).join(
            Servicio, Valoracion.id_servicio == Servicio.id
        ).where(
            Servicio.id_taller == taller_id
        )
    )
    total_valoraciones = result_count.scalar()
    
    # Obtener distribución de puntos (cuántas valoraciones de 1, 2, 3, 4, 5 estrellas)
    distribucion = {}
    for puntos in range(1, 6):
        result_dist = await db.execute(
            select(func.count(Valoracion.id)).select_from(Valoracion).join(
                Servicio, Valoracion.id_servicio == Servicio.id
            ).where(
                and_(
                    Servicio.id_taller == taller_id,
                    Valoracion.puntos == puntos
                )
            )
        )
        distribucion[f"{puntos}_estrellas"] = result_dist.scalar()
    
    return {
        "taller_id": taller_id,
        "nombre": taller.nombre,
        "puntos_promedio": float(taller.puntos),
        "total_valoraciones": total_valoraciones,
        "distribucion": distribucion
    }
