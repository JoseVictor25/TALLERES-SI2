"""
Servicio para gestionar solicitudes de servicio
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from geoalchemy2.functions import ST_Distance, ST_GeogFromText
from geoalchemy2.shape import to_shape, from_shape
from shapely.geometry import Point
from app.core.constants import ROL_TECNICO

from app.crud import (
    solicitud_servicio as solicitud_servicio_crud,
    diagnostico as diagnostico_crud,
    taller as taller_crud,
    configuracion_sistema as config_crud,
    solicitud_diagnostico as solicitud_diagnostico_crud
)
from app.models.solicitud_servicio import SolicitudServicio, SugeridoPorTipo
from app.models.taller import Taller, EstadoTaller
from app.models.tecnico_especialidad import TecnicoEspecialidad
from app.models.empleado import Empleado
from app.models.usuario import Usuario
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol
from app.models.especialidad import Especialidad
from app.models.requiere_especialidad import RequiereEspecialidad
from app.models.tipo_incidente import TipoIncidente
from app.models.incidente import Incidente

logger = logging.getLogger(__name__)

# Distancia máxima por defecto en kilómetros (reducida para que sean realmente talleres cercanos)
DEFAULT_MAX_DISTANCE_KM = 10.0


async def obtener_distancia_maxima(db: AsyncSession) -> float:
    """Obtiene la distancia máxima desde configuración del sistema"""
    config = await config_crud.get_by_clave(db, "distancia_maxima_taller_km")
    if config and config.valor:
        try:
            return float(config.valor)
        except ValueError:
            logger.warning(f"Valor inválido en configuración distancia_maxima_taller_km: {config.valor}")
    return DEFAULT_MAX_DISTANCE_KM


async def obtener_especialidades_requeridas(
    db: AsyncSession,
    id_diagnostico: int
) -> List[int]:
    """
    Obtiene las especialidades requeridas basándose en los tipos de incidentes
    asociados al diagnóstico.
    
    Flujo: diagnostico → incidente → tipo_incidente → categoria_incidente → requiere_especialidad → especialidad
    """
    # Obtener los tipos de incidentes del diagnóstico
    result = await db.execute(
        select(Incidente.id_tipo_incidente)
        .where(Incidente.id_diagnostico == id_diagnostico)
    )
    tipo_incidente_ids = [row[0] for row in result.all()]
    
    if not tipo_incidente_ids:
        return []
    
    # Obtener las categorías de incidentes de estos tipos
    result = await db.execute(
        select(TipoIncidente.id_categoria_incidente)
        .where(
            and_(
                TipoIncidente.id.in_(tipo_incidente_ids),
                TipoIncidente.id_categoria_incidente.isnot(None)
            )
        )
        .distinct()
    )
    categoria_ids = [row[0] for row in result.all()]
    
    if not categoria_ids:
        return []
    
    # Obtener las especialidades requeridas por estas categorías
    result = await db.execute(
        select(RequiereEspecialidad.id_especialidad)
        .where(RequiereEspecialidad.id_categoria_incidente.in_(categoria_ids))
        .distinct()
    )
    especialidad_ids = [row[0] for row in result.all()]
    
    return especialidad_ids

async def buscar_talleres_cercanos_con_especialidades(
    db: AsyncSession,
    ubicacion_cliente: tuple[float, float],  # (lat, lon)
    especialidades_requeridas: List[int],
    distancia_maxima_km: float
) -> List[Dict[str, Any]]:
    """
    Busca talleres cercanos que tengan técnicos con las especialidades requeridas
    
    Returns:
        Lista de diccionarios con: {taller, distancia_km, especialidades_disponibles}
    """
    lat, lon = ubicacion_cliente
    punto_cliente = f"POINT({lon} {lat})"
    
    # Convertir km a metros para PostGIS
    distancia_maxima_metros = distancia_maxima_km * 1000
    
    # Query para obtener talleres activos dentro del rango
    query = select(
        Taller,
        func.ST_Distance(
            Taller.ubicacion,
            func.ST_GeogFromText(punto_cliente)
        ).label('distancia')
    ).where(
        and_(
            Taller.estado == EstadoTaller.activo,
            func.ST_DWithin(
                Taller.ubicacion,
                func.ST_GeogFromText(punto_cliente),
                distancia_maxima_metros
            )
        )
    ).order_by('distancia')
    
    result = await db.execute(query)
    talleres_cercanos = result.all()
    
    if not talleres_cercanos:
        return []
    
    talleres_validos = []
    
    for taller, distancia in talleres_cercanos:
        # Si no hay especialidades requeridas, agregamos el taller directamente
        if not especialidades_requeridas:
            talleres_validos.append({
                'taller': taller,
                'distancia_km': round(distancia / 1000, 2),
                'especialidades_disponibles': []
            })
            continue

        # Verificar que el taller tenga técnicos con al menos una especialidad requerida
        especialidades_query = select(TecnicoEspecialidad.id_especialidad).join(
            Empleado, Empleado.id == TecnicoEspecialidad.id_empleado
        ).join(
            Usuario, Usuario.id == Empleado.id_usuario
        ).join(
            RolUsuario, RolUsuario.id_usuario == Usuario.id
        ).join(
            Rol, Rol.id == RolUsuario.id_rol
        ).where(
            and_(
                RolUsuario.id_taller == taller.id,
                Rol.nombre == ROL_TECNICO,
                TecnicoEspecialidad.id_especialidad.in_(especialidades_requeridas)
            )
        ).distinct()
        
        result_esp = await db.execute(especialidades_query)
        especialidades_disponibles = [row[0] for row in result_esp.all()]
        
        if especialidades_disponibles:
            # Obtener nombres de especialidades
            nombres_esp_query = select(Especialidad.nombre).where(
                Especialidad.id.in_(especialidades_disponibles)
            )
            result_nombres = await db.execute(nombres_esp_query)
            nombres_especialidades = [row[0] for row in result_nombres.all()]
            
            talleres_validos.append({
                'taller': taller,
                'distancia_km': round(distancia / 1000, 2),  # Convertir a km
                'especialidades_disponibles': nombres_especialidades
            })
    
    return talleres_validos


async def crear_solicitudes_servicio_automaticas(
    db: AsyncSession,
    id_diagnostico: int,
    id_persona: int
) -> Dict[str, Any]:
    """
    Crea solicitudes de servicio automáticas para talleres sugeridos
    
    Returns:
        {
            'solicitudes_creadas': int,
            'talleres_sugeridos': List[dict],
            'especialidades_requeridas': List[str]
        }
    """
    # Obtener el diagnóstico y su solicitud
    diagnostico = await diagnostico_crud.get(db, id_diagnostico)
    if not diagnostico:
        raise ValueError("Diagnóstico no encontrado")
    
    solicitud_diag = await solicitud_diagnostico_crud.get(db, diagnostico.id_solicitud_diagnostico)
    if not solicitud_diag:
        raise ValueError("Solicitud de diagnóstico no encontrada")
    
    if solicitud_diag.id_persona != id_persona:
        raise ValueError("No autorizado")
    
    # Obtener ubicación del cliente
    if not solicitud_diag.ubicacion:
        raise ValueError("La solicitud no tiene ubicación")
    
    point = to_shape(solicitud_diag.ubicacion)
    ubicacion_cliente = (point.y, point.x)  # (lat, lon)
    
    # Obtener especialidades requeridas
    especialidades_ids = await obtener_especialidades_requeridas(db, id_diagnostico)
    
    nombres_especialidades = []
    if not especialidades_ids:
        logger.info(f"No se encontraron especialidades requeridas para diagnóstico {id_diagnostico}, buscando todos los talleres cercanos")
    else:
        # Obtener nombres de especialidades
        result = await db.execute(
            select(Especialidad.nombre).where(Especialidad.id.in_(especialidades_ids))
        )
        nombres_especialidades = [row[0] for row in result.all()]
    
    # Obtener distancia máxima
    distancia_maxima = await obtener_distancia_maxima(db)
    
    # Buscar talleres cercanos con especialidades
    talleres_validos = await buscar_talleres_cercanos_con_especialidades(
        db,
        ubicacion_cliente,
        especialidades_ids,
        distancia_maxima
    )
    
    # Crear solicitudes de servicio
    solicitudes_creadas = 0
    talleres_sugeridos = []
    
    for taller_info in talleres_validos:
        taller = taller_info['taller']
        
        # Verificar si ya existe una solicitud para este taller
        existe = await solicitud_servicio_crud.get_by_taller_and_diagnostico(
            db, taller.id, id_diagnostico
        )
        
        if not existe:
            # Crear solicitud de servicio
            solicitud_data = {
                'ubicacion': solicitud_diag.ubicacion,
                'sugerido_por': SugeridoPorTipo.ia,
                'id_taller': taller.id,
                'id_diagnostico': id_diagnostico,
                'distancia_km': taller_info['distancia_km']
            }
            
            await solicitud_servicio_crud.create(db, solicitud_data)
            solicitudes_creadas += 1
        
        talleres_sugeridos.append({
            'id': taller.id,
            'nombre': taller.nombre,
            'distancia_km': taller_info['distancia_km'],
            'especialidades': taller_info['especialidades_disponibles']
        })
    
    await db.commit()
    
    return {
        'solicitudes_creadas': solicitudes_creadas,
        'talleres_sugeridos': talleres_sugeridos,
        'especialidades_requeridas': nombres_especialidades
    }


async def crear_solicitud_servicio_manual(
    db: AsyncSession,
    id_diagnostico: int,
    id_taller: int,
    id_persona: int,
    comentario: Optional[str] = None
) -> SolicitudServicio:
    """
    Crea una solicitud de servicio manual (elegida por el conductor)
    """
    # Verificar que el diagnóstico existe y pertenece al usuario
    diagnostico = await diagnostico_crud.get(db, id_diagnostico)
    if not diagnostico:
        raise ValueError("Diagnóstico no encontrado")
    
    solicitud_diag = await solicitud_diagnostico_crud.get(db, diagnostico.id_solicitud_diagnostico)
    if not solicitud_diag:
        raise ValueError("Solicitud de diagnóstico no encontrada")
    
    if solicitud_diag.id_persona != id_persona:
        raise ValueError("No autorizado")
    
    # Verificar que el taller existe
    taller = await taller_crud.get(db, id_taller)
    if not taller:
        raise ValueError("Taller no encontrado")
    
    # Verificar si ya existe una solicitud
    existe = await solicitud_servicio_crud.get_by_taller_and_diagnostico(
        db, id_taller, id_diagnostico
    )
    
    if existe:
        raise ValueError("Ya existe una solicitud de servicio para este taller")
    
    # Calcular distancia entre cliente y taller de manera confiable usando Python
    distancia_km = None
    if solicitud_diag.ubicacion and taller.ubicacion:
        try:
            from geoalchemy2.shape import to_shape
            import math
            p1 = to_shape(solicitud_diag.ubicacion) # point.x = lon, point.y = lat
            p2 = to_shape(taller.ubicacion)
            
            lon1, lat1 = p1.x, p1.y
            lon2, lat2 = p2.x, p2.y
            
            # Haversine formula
            R = 6371.0 # Radio de la tierra en km
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distancia_km = round(R * c, 2)
        except Exception as e:
            import logging
            logging.error(f"Error al calcular distancia_km: {e}")
            distancia_km = None
    
    # Crear solicitud
    solicitud_data = {
        'ubicacion': solicitud_diag.ubicacion,
        'comentario': comentario,
        'sugerido_por': SugeridoPorTipo.conductor,
        'id_taller': id_taller,
        'id_diagnostico': id_diagnostico,
        'distancia_km': distancia_km
    }
    
    solicitud = await solicitud_servicio_crud.create(db, solicitud_data)
    await db.commit()
    
    return solicitud
