from fastapi import APIRouter, Depends, HTTPException, status, Form
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.deps import get_current_persona
from app.models.persona import Persona
from app.schemas.solicitud_servicio import (
    SolicitudServicioResponse,
    SolicitudServicioCreate,
    TallerSugeridoResponse,
    TallerBasicInfo
)
from app.schemas.servicio import (
    ServicioClienteResponse,
    ServicioClienteListResponse,
    TallerInfoResponse,
    TecnicoAsignadoResponse,
    VehiculoAsignadoResponse,
    DiagnosticoDetalleResponse
)
from app.services import solicitud_servicio_service
from app.crud import (
    solicitud_servicio as solicitud_servicio_crud,
    diagnostico as diagnostico_crud,
    solicitud_diagnostico as solicitud_diagnostico_crud,
    taller as taller_crud,
    servicio as servicio_crud,
    servicio_tecnico as servicio_tecnico_crud,
    servicio_vehiculo as servicio_vehiculo_crud,
    empleado as empleado_crud
)
from app.models.vehiculo_taller import VehiculoTaller
from geoalchemy2.shape import to_shape
from sqlalchemy import select

router = APIRouter(prefix="/servicios", tags=["Servicios"])


@router.post("/{diagnostico_id}/generar-solicitudes", status_code=status.HTTP_201_CREATED)
async def generar_solicitudes_automaticas(
    diagnostico_id: int,
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Genera solicitudes de servicio automáticas para talleres sugeridos
    basándose en las especialidades requeridas y la ubicación del cliente
    """
    try:
        resultado = await solicitud_servicio_service.crear_solicitudes_servicio_automaticas(
            db=db,
            id_diagnostico=diagnostico_id,
            id_persona=current_persona.id
        )
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar solicitudes: {str(e)}")


@router.get("/{diagnostico_id}/talleres-sugeridos", response_model=List[TallerSugeridoResponse])
async def listar_talleres_sugeridos(
    diagnostico_id: int,
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista todos los talleres sugeridos y otros talleres cercanos,
    indicando cuáles ya tienen solicitud de servicio
    """
    # Verificar que el diagnóstico pertenece al usuario
    diagnostico = await diagnostico_crud.get(db, diagnostico_id)
    if not diagnostico:
        raise HTTPException(status_code=404, detail="Diagnóstico no encontrado")
    
    solicitud_diag = await solicitud_diagnostico_crud.get(db, diagnostico.id_solicitud_diagnostico)
    if not solicitud_diag or solicitud_diag.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Obtener ubicación del cliente
    if not solicitud_diag.ubicacion:
        raise HTTPException(status_code=400, detail="La solicitud no tiene ubicación")
    
    point = to_shape(solicitud_diag.ubicacion)
    ubicacion_cliente = (point.y, point.x)
    
    # Obtener especialidades requeridas
    especialidades_ids = await solicitud_servicio_service.obtener_especialidades_requeridas(
        db, diagnostico_id
    )
    
    # Obtener distancia máxima
    distancia_maxima = await solicitud_servicio_service.obtener_distancia_maxima(db)
    
    # Buscar talleres cercanos con especialidades
    talleres_info = await solicitud_servicio_service.buscar_talleres_cercanos_con_especialidades(
        db,
        ubicacion_cliente,
        especialidades_ids,
        distancia_maxima
    )
    
    # Obtener solicitudes existentes
    solicitudes_existentes = await solicitud_servicio_crud.get_by_diagnostico(db, diagnostico_id)
    solicitudes_map = {s.id_taller: s for s in solicitudes_existentes}
    
    # Construir respuesta
    resultado = []
    for taller_info in talleres_info:
        taller = taller_info['taller']
        tiene_solicitud = taller.id in solicitudes_map
        
        resultado.append({
            'taller': TallerBasicInfo(
                id=taller.id,
                nombre=taller.nombre,
                telefono=taller.telefono,
                email=taller.email,
                puntos=float(taller.puntos)
            ),
            'distancia_km': taller_info['distancia_km'],
            'tiene_solicitud': tiene_solicitud,
            'solicitud_id': solicitudes_map[taller.id].id if tiene_solicitud else None,
            'estado_solicitud': str(solicitudes_map[taller.id].estado.value) if tiene_solicitud else None,
            'costo_estimado': float(solicitudes_map[taller.id].costo_estimado) if tiene_solicitud and solicitudes_map[taller.id].costo_estimado is not None else None,
            'especialidades_disponibles': taller_info['especialidades_disponibles']
        })
    
    return resultado


@router.post("/{diagnostico_id}/solicitar-taller", status_code=status.HTTP_201_CREATED)
async def solicitar_servicio_taller(
    diagnostico_id: int,
    id_taller: int = Form(...),
    comentario: Optional[str] = Form(None),
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Crea una solicitud de servicio manual para un taller específico
    (elegido por el conductor)
    """
    try:
        solicitud = await solicitud_servicio_service.crear_solicitud_servicio_manual(
            db=db,
            id_diagnostico=diagnostico_id,
            id_taller=id_taller,
            id_persona=current_persona.id,
            comentario=comentario
        )
        
        # Convertir ubicacion a string
        if solicitud.ubicacion:
            point = to_shape(solicitud.ubicacion)
            solicitud.ubicacion = f"{point.y},{point.x}"
        
        return solicitud
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{diagnostico_id}/solicitudes", response_model=List[SolicitudServicioResponse])
async def listar_solicitudes_servicio(
    diagnostico_id: int,
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista todas las solicitudes de servicio para un diagnóstico
    """
    # Verificar que el diagnóstico pertenece al usuario
    diagnostico = await diagnostico_crud.get(db, diagnostico_id)
    if not diagnostico:
        raise HTTPException(status_code=404, detail="Diagnóstico no encontrado")
    
    solicitud_diag = await solicitud_diagnostico_crud.get(db, diagnostico.id_solicitud_diagnostico)
    if not solicitud_diag or solicitud_diag.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Obtener solicitudes
    solicitudes = await solicitud_servicio_crud.get_by_diagnostico(db, diagnostico_id)
    
    # Convertir ubicaciones a string
    for solicitud in solicitudes:
        if solicitud.ubicacion:
            point = to_shape(solicitud.ubicacion)
            solicitud.ubicacion = f"{point.y},{point.x}"
    
    return solicitudes


@router.delete("/{solicitud_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancelar_solicitud_servicio(
    solicitud_id: int,
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancela una solicitud de servicio (solo si está pendiente)
    """
    solicitud = await solicitud_servicio_crud.get(db, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Verificar que pertenece al usuario
    diagnostico = await diagnostico_crud.get(db, solicitud.id_diagnostico)
    solicitud_diag = await solicitud_diagnostico_crud.get(db, diagnostico.id_solicitud_diagnostico)
    
    if solicitud_diag.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Solo se puede cancelar si está pendiente
    from app.models.solicitud_servicio import EstadoSolicitudServicio
    if solicitud.estado != EstadoSolicitudServicio.pendiente:
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden cancelar solicitudes en estado pendiente"
        )
    
    await solicitud_servicio_crud.update_estado(
        db, solicitud_id, EstadoSolicitudServicio.cancelada
    )
    await db.commit()
    
    return None


@router.patch("/{solicitud_id}/comentario", status_code=status.HTTP_200_OK)
async def actualizar_comentario(
    solicitud_id: int,
    comentario: str = Form(...),
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza el comentario de una solicitud de servicio existente
    """
    solicitud = await solicitud_servicio_crud.get(db, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Verificar que pertenece al usuario
    diagnostico = await diagnostico_crud.get(db, solicitud.id_diagnostico)
    solicitud_diag = await solicitud_diagnostico_crud.get(db, diagnostico.id_solicitud_diagnostico)
    
    if solicitud_diag.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Actualizar comentario
    solicitud.comentario = comentario.strip() if comentario else None
    await db.commit()
    await db.refresh(solicitud)
    
    # Convertir ubicacion a string
    if solicitud.ubicacion:
        point = to_shape(solicitud.ubicacion)
        solicitud.ubicacion = f"{point.y},{point.x}"
    
    return solicitud


@router.get("/taller/{taller_id}/ubicacion")
async def obtener_ubicacion_taller(
    taller_id: int,
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene la ubicación de un taller para mostrar en el mapa
    """
    taller = await taller_crud.get(db, taller_id)
    if not taller:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    
    # Convertir ubicacion a string
    if taller.ubicacion:
        point = to_shape(taller.ubicacion)
        return {
            "id": taller.id,
            "nombre": taller.nombre,
            "ubicacion": f"{point.y},{point.x}",  # lat,lon
            "telefono": taller.telefono,
            "email": taller.email
        }
    
    raise HTTPException(status_code=404, detail="El taller no tiene ubicación registrada")



# ============================================================
# ENDPOINTS PARA CLIENTE MÓVIL - SERVICIOS
# ============================================================

@router.get("/mis-servicios/actual", response_model=Optional[ServicioClienteResponse])
async def obtener_servicio_actual(
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el servicio actual (activo) del cliente.
    Retorna el servicio en estado 'creado' o 'en_proceso' más reciente.
    """
    from app.models.servicio import EstadoServicio
    from app.models.solicitud_servicio import SolicitudServicio
    
    # Buscar servicios activos del cliente a través de sus diagnósticos
    result = await db.execute(
        select(servicio_crud.model)
        .join(SolicitudServicio, SolicitudServicio.id == servicio_crud.model.id_solicitud_servicio)
        .join(diagnostico_crud.model, diagnostico_crud.model.id == SolicitudServicio.id_diagnostico)
        .join(solicitud_diagnostico_crud.model, solicitud_diagnostico_crud.model.id == diagnostico_crud.model.id_solicitud_diagnostico)
        .where(
            solicitud_diagnostico_crud.model.id_persona == current_persona.id,
            servicio_crud.model.estado.in_([
                EstadoServicio.creado, 
                EstadoServicio.tecnico_asignado,
                EstadoServicio.en_camino,
                EstadoServicio.en_lugar,
                EstadoServicio.en_atencion
            ])
        )
        .order_by(servicio_crud.model.fecha.desc())
    )
    
    servicio = result.scalars().first()
    
    if not servicio:
        return None
    
    # Obtener información del taller
    taller = await taller_crud.get(db, servicio.id_taller)
    taller_ubicacion = None
    if taller.ubicacion:
        point = to_shape(taller.ubicacion)
        taller_ubicacion = f"{point.y},{point.x}"
    
    taller_info = TallerInfoResponse(
        id=taller.id,
        nombre=taller.nombre,
        telefono=taller.telefono,
        email=taller.email,
        direccion=None,  # Taller model doesn't have direccion field
        ubicacion=taller_ubicacion,
        puntos=float(taller.puntos)
    )
    
    # Obtener técnicos asignados
    tecnicos_asignados = await servicio_tecnico_crud.get_by_servicio(db, servicio.id)
    tecnicos_response = []
    for asignacion in tecnicos_asignados:
        empleado = await empleado_crud.get_with_usuario(db, asignacion.id_empleado)
        if empleado:
            tecnicos_response.append(TecnicoAsignadoResponse(
                id_empleado=empleado.id,
                nombre_completo=empleado.usuario.nombre
            ))
    
    # Obtener vehículos asignados
    vehiculos_asignados = await servicio_vehiculo_crud.get_by_servicio(db, servicio.id)
    vehiculos_response = []
    for asignacion in vehiculos_asignados:
        result_v = await db.execute(
            select(VehiculoTaller).where(VehiculoTaller.id == asignacion.id_vehiculo_taller)
        )
        vehiculo = result_v.scalar_one_or_none()
        if vehiculo:
            vehiculos_response.append(VehiculoAsignadoResponse(
                id_vehiculo_taller=vehiculo.id,
                matricula=vehiculo.matricula,
                marca=vehiculo.marca,
                modelo=vehiculo.modelo
            ))
    
    # Obtener ubicación del cliente (de la solicitud original)
    solicitud = await solicitud_servicio_crud.get(db, servicio.id_solicitud_servicio)
    ubicacion_cliente = None
    if solicitud and solicitud.ubicacion:
        point = to_shape(solicitud.ubicacion)
        ubicacion_cliente = f"{point.y},{point.x}"
    
    # Obtener información del diagnóstico
    diagnostico = await diagnostico_crud.get(db, solicitud.id_diagnostico)
    diagnostico_response = None
    if diagnostico:
        diagnostico_response = DiagnosticoDetalleResponse(
            id=diagnostico.id,
            descripcion=diagnostico.descripcion,
            nivel_confianza=diagnostico.nivel_confianza,
            fecha=diagnostico.fecha
        )
    
    return ServicioClienteResponse(
        id=servicio.id,
        fecha=servicio.fecha,
        estado=servicio.estado.value,
        taller=taller_info,
        tecnicos_asignados=tecnicos_response,
        vehiculos_asignados=vehiculos_response,
        ubicacion_cliente=ubicacion_cliente,
        diagnostico=diagnostico_response
    )


@router.get("/mis-servicios/historial", response_model=List[ServicioClienteListResponse])
async def obtener_historial_servicios(
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el historial de servicios completados o cancelados del cliente.
    """
    from app.models.servicio import EstadoServicio
    from app.models.solicitud_servicio import SolicitudServicio
    
    # Buscar servicios completados/cancelados del cliente
    result = await db.execute(
        select(servicio_crud.model)
        .join(SolicitudServicio, SolicitudServicio.id == servicio_crud.model.id_solicitud_servicio)
        .join(diagnostico_crud.model, diagnostico_crud.model.id == SolicitudServicio.id_diagnostico)
        .join(solicitud_diagnostico_crud.model, solicitud_diagnostico_crud.model.id == diagnostico_crud.model.id_solicitud_diagnostico)
        .where(
            solicitud_diagnostico_crud.model.id_persona == current_persona.id,
            servicio_crud.model.estado.in_([EstadoServicio.finalizado, EstadoServicio.cancelado])
        )
        .order_by(servicio_crud.model.fecha.desc())
    )
    
    servicios = result.scalars().all()
    
    # Construir respuesta
    resultado = []
    for servicio in servicios:
        # Obtener taller
        taller = await taller_crud.get(db, servicio.id_taller)
        
        # Obtener diagnóstico
        solicitud = await solicitud_servicio_crud.get(db, servicio.id_solicitud_servicio)
        diagnostico = await diagnostico_crud.get(db, solicitud.id_diagnostico)
        
        resultado.append(ServicioClienteListResponse(
            id=servicio.id,
            fecha=servicio.fecha,
            estado=servicio.estado.value,
            taller_nombre=taller.nombre,
            diagnostico_descripcion=diagnostico.descripcion if diagnostico else None
        ))
    
    return resultado


@router.get("/mis-servicios/{servicio_id}/detalle", response_model=ServicioClienteResponse)
async def obtener_detalle_servicio_cliente(
    servicio_id: int,
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el detalle completo de un servicio específico del cliente.
    """
    from app.models.solicitud_servicio import SolicitudServicio
    
    # Obtener servicio y verificar que pertenece al cliente
    servicio = await servicio_crud.get(db, servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    # Verificar que el servicio pertenece al cliente
    solicitud = await solicitud_servicio_crud.get(db, servicio.id_solicitud_servicio)
    diagnostico = await diagnostico_crud.get(db, solicitud.id_diagnostico)
    solicitud_diag = await solicitud_diagnostico_crud.get(db, diagnostico.id_solicitud_diagnostico)
    
    if solicitud_diag.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Obtener información del taller
    taller = await taller_crud.get(db, servicio.id_taller)
    taller_ubicacion = None
    if taller.ubicacion:
        point = to_shape(taller.ubicacion)
        taller_ubicacion = f"{point.y},{point.x}"
    
    taller_info = TallerInfoResponse(
        id=taller.id,
        nombre=taller.nombre,
        telefono=taller.telefono,
        email=taller.email,
        direccion=None,  # Taller model doesn't have direccion field
        ubicacion=taller_ubicacion,
        puntos=float(taller.puntos)
    )
    
    # Obtener técnicos asignados
    tecnicos_asignados = await servicio_tecnico_crud.get_by_servicio(db, servicio.id)
    tecnicos_response = []
    for asignacion in tecnicos_asignados:
        empleado = await empleado_crud.get_with_usuario(db, asignacion.id_empleado)
        if empleado:
            tecnicos_response.append(TecnicoAsignadoResponse(
                id_empleado=empleado.id,
                nombre_completo=empleado.usuario.nombre
            ))
    
    # Obtener vehículos asignados
    vehiculos_asignados = await servicio_vehiculo_crud.get_by_servicio(db, servicio.id)
    vehiculos_response = []
    for asignacion in vehiculos_asignados:
        result_v = await db.execute(
            select(VehiculoTaller).where(VehiculoTaller.id == asignacion.id_vehiculo_taller)
        )
        vehiculo = result_v.scalar_one_or_none()
        if vehiculo:
            vehiculos_response.append(VehiculoAsignadoResponse(
                id_vehiculo_taller=vehiculo.id,
                matricula=vehiculo.matricula,
                marca=vehiculo.marca,
                modelo=vehiculo.modelo
            ))
    
    # Obtener ubicación del cliente
    ubicacion_cliente = None
    if solicitud.ubicacion:
        point = to_shape(solicitud.ubicacion)
        ubicacion_cliente = f"{point.y},{point.x}"
    
    # Obtener información del diagnóstico
    diagnostico_response = None
    if diagnostico:
        diagnostico_response = DiagnosticoDetalleResponse(
            id=diagnostico.id,
            descripcion=diagnostico.descripcion,
            nivel_confianza=diagnostico.nivel_confianza,
            fecha=diagnostico.fecha
        )
    
    return ServicioClienteResponse(
        id=servicio.id,
        fecha=servicio.fecha,
        estado=servicio.estado.value,
        taller=taller_info,
        tecnicos_asignados=tecnicos_response,
        vehiculos_asignados=vehiculos_response,
        ubicacion_cliente=ubicacion_cliente,
        diagnostico=diagnostico_response
    )

