from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.deps import get_current_persona
from app.models.persona import Persona
from app.schemas.diagnostico import SolicitudDiagnosticoResponse
from app.services import diagnostico_service
from app.crud import solicitud_diagnostico as solicitud_crud, tipo_incidente as tipo_incidente_crud, incidente as incidente_crud
from decimal import Decimal

router = APIRouter(prefix="/diagnosticos", tags=["Diagnósticos"])


@router.get("/tipos-incidentes", response_model=list[dict])
async def listar_tipos_incidentes_publico(
    db: AsyncSession = Depends(get_db)
):
    """Lista todos los tipos de incidentes disponibles (endpoint público)"""
    tipos = await tipo_incidente_crud.get_all(db)
    return [{"id": t.id, "concepto": t.concepto, "prioridad": t.prioridad} for t in tipos]


@router.post("/", response_model=SolicitudDiagnosticoResponse, status_code=status.HTTP_201_CREATED)
async def crear_solicitud(
    descripcion: str = Form(..., min_length=5, description="Descripción del problema"),
    ubicacion: str = Form(..., description="Ubicación en formato 'lat,lon'"),
    matricula: Optional[str] = Form(None, description="Matrícula del vehículo"),
    marca: Optional[str] = Form(None, description="Marca del vehículo"),
    modelo: Optional[str] = Form(None, description="Modelo del vehículo"),
    anio: Optional[int] = Form(None, description="Año del vehículo"),
    color: Optional[str] = Form(None, description="Color del vehículo"),
    tipo_vehiculo: Optional[str] = Form(None, description="Tipo de vehículo"),
    foto1: Optional[UploadFile] = File(None, description="Primera foto (opcional)"),
    foto2: Optional[UploadFile] = File(None, description="Segunda foto (opcional)"),
    foto3: Optional[UploadFile] = File(None, description="Tercera foto (opcional)"),
    audio: Optional[UploadFile] = File(None, description="Audio del problema (opcional)"),
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Crea una solicitud de diagnóstico con evidencias.
    
    - **descripcion**: Descripción del problema vehicular
    - **ubicacion**: Coordenadas en formato "lat,lon" (ej: "-17.783333,-63.182222")
    - **matricula**: Matrícula del vehículo (opcional)
    - **foto1, foto2, foto3**: Hasta 3 fotos del problema (opcional)
    - **audio**: Grabación de audio describiendo el problema (opcional)
    """
    # Recopilar fotos no vacías
    fotos = []
    for foto in [foto1, foto2, foto3]:
        if foto and foto.filename:  # Verificar que el archivo no esté vacío
            fotos.append(foto)
    
    # Validar número de fotos
    if len(fotos) > 3:
        raise HTTPException(status_code=400, detail="Máximo 3 fotos permitidas")

    # Data vehiculo opcional
    vehiculo_data = None
    if matricula and (marca and modelo and anio):
        vehiculo_data = {
            "matricula": matricula, 
            "marca": marca, 
            "modelo": modelo, 
            "anio": anio, 
            "color": color, 
            "tipo": tipo_vehiculo
        }

    try:
        solicitud = await diagnostico_service.crear_solicitud_diagnostico(
            db=db,
            id_persona=current_persona.id,
            descripcion=descripcion,
            ubicacion_str=ubicacion,
            matricula=matricula,
            vehiculo_data=vehiculo_data,
            fotos=fotos if fotos else None,
            audio=audio if audio and audio.filename else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Convertir ubicacion a string para serialización
    from geoalchemy2.shape import to_shape
    if solicitud.ubicacion:
        point = to_shape(solicitud.ubicacion)
        solicitud.ubicacion = f"{point.y},{point.x}"
    
    return solicitud


@router.post("/multiple-files", response_model=SolicitudDiagnosticoResponse, status_code=status.HTTP_201_CREATED)
async def crear_solicitud_multiple_files(
    descripcion: str = Form(..., min_length=5),
    ubicacion: str = Form(...),
    matricula: Optional[str] = Form(None),
    marca: Optional[str] = Form(None),
    modelo: Optional[str] = Form(None),
    anio: Optional[int] = Form(None),
    color: Optional[str] = Form(None),
    tipo_vehiculo: Optional[str] = Form(None),
    fotos: Optional[List[UploadFile]] = File(None),
    audio: Optional[UploadFile] = File(None),
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint alternativo para crear solicitud con múltiples archivos.
    Usar este endpoint desde código/Postman, no desde Swagger UI.
    """
    # Validaciones simples
    if fotos and len(fotos) > 3:
        raise HTTPException(status_code=400, detail="Máximo 3 fotos permitidas")

    # Data vehiculo opcional
    vehiculo_data = None
    if matricula and (marca and modelo and anio):
        vehiculo_data = {"matricula": matricula, "marca": marca, "modelo": modelo, "anio": anio, "color": color, "tipo": tipo_vehiculo}

    try:
        solicitud = await diagnostico_service.crear_solicitud_diagnostico(
            db=db,
            id_persona=current_persona.id,
            descripcion=descripcion,
            ubicacion_str=ubicacion,
            matricula=matricula,
            vehiculo_data=vehiculo_data,
            fotos=fotos,
            audio=audio
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return solicitud


@router.get("/mis-solicitudes", response_model=list[SolicitudDiagnosticoResponse])
async def listar_mis_solicitudes(
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.orm import selectinload, joinedload
    from sqlalchemy import select
    from app.models.solicitud_diagnostico import SolicitudDiagnostico
    from app.models.diagnostico import Diagnostico
    from app.models.solicitud_servicio import SolicitudServicio, EstadoSolicitudServicio
    from app.models.incidente import Incidente
    
    # Usar el CRUD que ya carga correctamente las relaciones base
    items, _ = await solicitud_crud.get_by_persona_paginated(db, current_persona.id, 0, 100)
    
    # Convertir ubicaciones a string para serialización y verificar si todas las solicitudes de servicio están rechazadas
    from geoalchemy2.shape import to_shape
    for solicitud in items:
        if solicitud.ubicacion:
            point = to_shape(solicitud.ubicacion)
            solicitud.ubicacion = f"{point.y},{point.x}"
            
        # Si tiene diagnóstico, verificar el estado de sus solicitudes de servicio
        if solicitud.diagnostico and hasattr(solicitud.diagnostico, 'solicitudes_servicio'):
            servicios = solicitud.diagnostico.solicitudes_servicio
            if servicios and len(servicios) > 0:
                todas_rechazadas = all(s.estado == EstadoSolicitudServicio.rechazada for s in servicios)
                alguna_activa = any(s.estado in [EstadoSolicitudServicio.pendiente, EstadoSolicitudServicio.cotizada, EstadoSolicitudServicio.aceptada] for s in servicios)
                
                if todas_rechazadas and not alguna_activa:
                    from app.models.solicitud_diagnostico import EstadoSolicitudDiagnostico
                    solicitud.estado = EstadoSolicitudDiagnostico.rechazada
    
    return items


@router.get("/{solicitud_id}", response_model=SolicitudDiagnosticoResponse)
async def obtener_solicitud(solicitud_id: int, current_persona: Persona = Depends(get_current_persona), db: AsyncSession = Depends(get_db)):
    solicitud = await solicitud_crud.get(db, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if solicitud.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Convertir ubicacion a string para serialización
    from geoalchemy2.shape import to_shape
    if solicitud.ubicacion:
        point = to_shape(solicitud.ubicacion)
        solicitud.ubicacion = f"{point.y},{point.x}"
    
    return solicitud


@router.post("/{solicitud_id}/cancel", status_code=204)
async def cancelar_solicitud(solicitud_id: int, current_persona: Persona = Depends(get_current_persona), db: AsyncSession = Depends(get_db)):
    solicitud = await solicitud_crud.get(db, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if solicitud.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    from app.models.solicitud_diagnostico import EstadoSolicitudDiagnostico
    if solicitud.estado != EstadoSolicitudDiagnostico.pendiente:
        raise HTTPException(status_code=400, detail="Solo se puede cancelar solicitudes en estado 'pendiente'")
    await solicitud_crud.update_estado(db, solicitud_id, EstadoSolicitudDiagnostico.cancelada)
    await db.commit()
    return None



@router.post("/{solicitud_id}/sugerir", status_code=201)
async def sugerir_incidente(solicitud_id: int, concepto: str = Form(...), current_persona: Persona = Depends(get_current_persona), db: AsyncSession = Depends(get_db)):
    solicitud = await solicitud_crud.get(db, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if solicitud.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    # Debe existir diagnóstico para asociar la sugerencia
    if not solicitud.diagnostico:
        raise HTTPException(status_code=400, detail="El diagnóstico aún no está disponible; solo puede sugerir después de recibir el diagnóstico")

    # obtener o crear tipo_incidente
    tipo = await tipo_incidente_crud.get_by_concepto(db, concepto)
    if not tipo:
        tipo = await tipo_incidente_crud.create(db, {"concepto": concepto, "prioridad": 3, "requiere_remolque": False})

    # crear incidente sugerido por conductor, nivel_confianza = 0.0 (no contado en promedio)
    await incidente_crud.create(db, {"id_diagnostico": solicitud.diagnostico.id, "id_tipo_incidente": tipo.id, "sugerido_por": "conductor", "nivel_confianza": Decimal("0.0")})
    await db.commit()
    return {"message": "Sugerencia registrada"}


@router.post("/{solicitud_id}/asociar-tipo", status_code=201)
async def asociar_tipo_incidente(
    solicitud_id: int,
    id_tipo_incidente: int = Form(...),
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """Asocia un tipo de incidente existente al diagnóstico"""
    solicitud = await solicitud_crud.get(db, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if solicitud.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    if not solicitud.diagnostico:
        raise HTTPException(status_code=400, detail="El diagnóstico aún no está disponible")

    # Verificar que el tipo existe
    tipo = await tipo_incidente_crud.get(db, id_tipo_incidente)
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de incidente no encontrado")

    # Verificar que no esté ya asociado
    existing = await incidente_crud.get_by_diagnostico_and_tipo(db, solicitud.diagnostico.id, id_tipo_incidente)
    if existing:
        raise HTTPException(status_code=400, detail="Este tipo de incidente ya está asociado")

    # Crear incidente asociado por conductor
    await incidente_crud.create(db, {
        "id_diagnostico": solicitud.diagnostico.id,
        "id_tipo_incidente": id_tipo_incidente,
        "sugerido_por": "conductor",
        "nivel_confianza": Decimal("1.0")
    })
    await db.commit()
    return {"message": "Tipo de incidente asociado correctamente"}


@router.delete("/{solicitud_id}/incidentes/{id_diagnostico}/{id_tipo_incidente}", status_code=204)
async def descartar_incidente(
    solicitud_id: int,
    id_diagnostico: int,
    id_tipo_incidente: int,
    current_persona: Persona = Depends(get_current_persona),
    db: AsyncSession = Depends(get_db)
):
    """Descarta/elimina un incidente del diagnóstico"""
    solicitud = await solicitud_crud.get(db, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if solicitud.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")

    if not solicitud.diagnostico:
        raise HTTPException(status_code=400, detail="El diagnóstico no está disponible")

    # Verificar que el incidente pertenece a este diagnóstico
    incidente = await incidente_crud.get_by_diagnostico_and_tipo(db, id_diagnostico, id_tipo_incidente)
    if not incidente or incidente.id_diagnostico != solicitud.diagnostico.id:
        raise HTTPException(status_code=404, detail="Incidente no encontrado en este diagnóstico")

    # Eliminar el incidente
    await db.delete(incidente)
    await db.commit()
    return None


@router.post("/{solicitud_id}/reintentar", status_code=200)
async def reintentar(solicitud_id: int, current_persona: Persona = Depends(get_current_persona), db: AsyncSession = Depends(get_db)):
    solicitud = await solicitud_crud.get(db, solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if solicitud.id_persona != current_persona.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    resultado = await diagnostico_service.reintentar_procesamiento(db, solicitud_id)
    if not resultado:
        raise HTTPException(status_code=500, detail="Fallo al reintentar")
    return resultado
