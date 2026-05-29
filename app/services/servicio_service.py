"""
Servicio para gestionar servicios de taller
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.crud import (
    servicio as servicio_crud,
    servicio_tecnico as servicio_tecnico_crud,
    servicio_vehiculo as servicio_vehiculo_crud,
    solicitud_servicio as solicitud_servicio_crud,
    empleado as empleado_crud,
)
from app.models.servicio import Servicio, EstadoServicio
from app.models.servicio_tecnico import ServicioTecnico
from app.models.servicio_vehiculo import ServicioVehiculo
from app.models.solicitud_servicio import SolicitudServicio, EstadoSolicitudServicio
from app.models.empleado import Empleado, EstadoEmpleado
from app.models.vehiculo_taller import VehiculoTaller, EstadoVehiculoTaller
from app.models.usuario import Usuario
from app.models.rol_usuario import RolUsuario
from app.models.rol import Rol
from app.core.constants import ROL_TECNICO

logger = logging.getLogger(__name__)


async def obtener_solicitudes_recientes(
    db: AsyncSession,
    id_taller: int,
    minutos: int = 60
) -> List[SolicitudServicio]:
    """
    Obtiene solicitudes de servicio recientes (últimos X minutos) para un taller
    """
    tiempo_limite = datetime.utcnow() - timedelta(minutes=minutos)
    
    result = await db.execute(
        select(SolicitudServicio).where(
            and_(
                SolicitudServicio.id_taller == id_taller,
                SolicitudServicio.estado == EstadoSolicitudServicio.pendiente,
                SolicitudServicio.fecha >= tiempo_limite
            )
        ).order_by(SolicitudServicio.fecha.desc())
    )
    
    return list(result.scalars().all())


async def obtener_solicitudes_historicas(
    db: AsyncSession,
    id_taller: int
) -> List[SolicitudServicio]:
    """
    Obtiene todas las solicitudes de servicio (historial) para un taller
    """
    result = await db.execute(
        select(SolicitudServicio).where(
            SolicitudServicio.id_taller == id_taller
        ).order_by(SolicitudServicio.fecha.desc())
    )
    
    return list(result.scalars().all())


async def obtener_tecnicos_disponibles(
    db: AsyncSession,
    id_taller: int
) -> List[Dict[str, Any]]:
    """
    Obtiene técnicos disponibles (no en servicio) de un taller
    """
    # Obtener empleados con rol "tecnico" en el taller
    result = await db.execute(
        select(Empleado).distinct().join(
            Usuario, Usuario.id == Empleado.id_usuario
        ).join(
            RolUsuario, RolUsuario.id_usuario == Usuario.id
        ).join(
            Rol, Rol.id == RolUsuario.id_rol
        ).where(
            and_(
                RolUsuario.id_taller == id_taller,
                Rol.nombre == ROL_TECNICO,
                Empleado.estado == EstadoEmpleado.disponible
            )
        ).options(selectinload(Empleado.usuario)).distinct()
    )
    
    empleados = result.scalars().all()
    
    # Obtener especialidades de cada técnico
    tecnicos_info = []
    for empleado in empleados:
        # Obtener especialidades
        from app.models.tecnico_especialidad import TecnicoEspecialidad
        from app.models.especialidad import Especialidad
        
        result_esp = await db.execute(
            select(Especialidad.nombre).join(
                TecnicoEspecialidad,
                TecnicoEspecialidad.id_especialidad == Especialidad.id
            ).where(
                TecnicoEspecialidad.id_empleado == empleado.id
            )
        )
        especialidades = [row[0] for row in result_esp.all()]
        
        tecnicos_info.append({
            'id': empleado.id,
            'nombre_completo': empleado.usuario.nombre,
            'especialidades': especialidades,
            'estado': empleado.estado.value
        })
    
    return tecnicos_info


async def obtener_vehiculos_disponibles(
    db: AsyncSession,
    id_taller: int
) -> List[VehiculoTaller]:
    """
    Obtiene vehículos disponibles (no en servicio) de un taller
    """
    result = await db.execute(
        select(VehiculoTaller).where(
            and_(
                VehiculoTaller.id_taller == id_taller,
                VehiculoTaller.estado == EstadoVehiculoTaller.disponible
            )
        )
    )
    
    return list(result.scalars().all())


async def aceptar_solicitud_servicio(
    db: AsyncSession,
    id_solicitud: int,
    id_taller: int,
    tecnicos_ids: List[int],
    vehiculos_ids: List[int]
) -> Servicio:
    """
    Acepta una solicitud de servicio y crea un servicio con técnicos y vehículos asignados.
    También cancela automáticamente todas las demás solicitudes del mismo diagnóstico hacia otros talleres.
    """
    # Verificar que la solicitud existe y pertenece al taller
    solicitud = await solicitud_servicio_crud.get(db, id_solicitud)
    if not solicitud:
        raise ValueError("Solicitud no encontrada")
    
    if solicitud.id_taller != id_taller:
        raise ValueError("La solicitud no pertenece a este taller")
    
    if solicitud.estado != EstadoSolicitudServicio.pendiente:
        raise ValueError("Solo se pueden aceptar solicitudes en estado pendiente")
    
    # Verificar que no exista ya un servicio para esta solicitud
    servicio_existente = await servicio_crud.get_by_solicitud(db, id_solicitud)
    if servicio_existente:
        raise ValueError("Ya existe un servicio para esta solicitud")
    
    # Validar que se proporcionaron técnicos y vehículos
    if not tecnicos_ids:
        raise ValueError("Debe asignar al menos un técnico")
    
    if not vehiculos_ids:
        raise ValueError("Debe asignar al menos un vehículo")
    
    # Crear el servicio
    servicio_data = {
        'id_taller': id_taller,
        'id_solicitud_servicio': id_solicitud,
        'estado': EstadoServicio.tecnico_asignado  # Usar el nuevo valor del enum
    }
    
    servicio = await servicio_crud.create(db, servicio_data)
    await db.flush()
    
    # Asignar técnicos
    for tecnico_id in tecnicos_ids:
        # Verificar que el técnico existe y está disponible
        empleado = await empleado_crud.get(db, tecnico_id)
        if not empleado:
            raise ValueError(f"Técnico {tecnico_id} no encontrado")
        
        if empleado.estado != EstadoEmpleado.disponible:
            raise ValueError(f"Técnico {tecnico_id} no está disponible")
        
        # Crear asignación
        await servicio_tecnico_crud.create(db, {
            'id_servicio': servicio.id,
            'id_empleado': tecnico_id
        })
        
        # Cambiar estado del técnico a en_servicio
        empleado.estado = EstadoEmpleado.en_servicio
    
    # Asignar vehículos
    for vehiculo_id in vehiculos_ids:
        # Verificar que el vehículo existe y está disponible
        result = await db.execute(
            select(VehiculoTaller).where(VehiculoTaller.id == vehiculo_id)
        )
        vehiculo = result.scalar_one_or_none()
        
        if not vehiculo:
            raise ValueError(f"Vehículo {vehiculo_id} no encontrado")
        
        if vehiculo.estado != EstadoVehiculoTaller.disponible:
            raise ValueError(f"Vehículo {vehiculo_id} no está disponible")
        
        # Crear asignación
        await servicio_vehiculo_crud.create(db, {
            'id_servicio': servicio.id,
            'id_vehiculo_taller': vehiculo_id
        })
        
        # Cambiar estado del vehículo a en_servicio
        vehiculo.estado = EstadoVehiculoTaller.en_servicio
    
    # Actualizar estado de la solicitud a aceptada
    await solicitud_servicio_crud.update_estado(
        db, 
        id_solicitud, 
        EstadoSolicitudServicio.aceptada
    )
    
    # CANCELAR TODAS LAS DEMÁS SOLICITUDES DEL MISMO DIAGNÓSTICO
    # Obtener el id_diagnostico de la solicitud aceptada
    id_diagnostico = solicitud.id_diagnostico
    
    if id_diagnostico:
        # Buscar todas las solicitudes pendientes del mismo diagnóstico (excepto la actual)
        result = await db.execute(
            select(SolicitudServicio).where(
                and_(
                    SolicitudServicio.id_diagnostico == id_diagnostico,
                    SolicitudServicio.id != id_solicitud,
                    SolicitudServicio.estado == EstadoSolicitudServicio.pendiente
                )
            )
        )
        
        solicitudes_a_cancelar = result.scalars().all()
        
        # Cancelar cada solicitud
        for sol in solicitudes_a_cancelar:
            sol.estado = EstadoSolicitudServicio.cancelada
        
        logger.info(f"Se cancelaron {len(solicitudes_a_cancelar)} solicitudes del diagnóstico {id_diagnostico}")
    
    await db.commit()
    await db.refresh(servicio)
    
    return servicio


async def rechazar_solicitud_servicio(
    db: AsyncSession,
    id_solicitud: int,
    id_taller: int
) -> SolicitudServicio:
    """
    Rechaza una solicitud de servicio
    """
    solicitud = await solicitud_servicio_crud.get(db, id_solicitud)
    if not solicitud:
        raise ValueError("Solicitud no encontrada")
    
    if solicitud.id_taller != id_taller:
        raise ValueError("La solicitud no pertenece a este taller")
    
    if solicitud.estado != EstadoSolicitudServicio.pendiente:
        raise ValueError("Solo se pueden rechazar solicitudes en estado pendiente")
    
    await solicitud_servicio_crud.update_estado(
        db,
        id_solicitud,
        EstadoSolicitudServicio.rechazada
    )
    
    await db.commit()
    await db.refresh(solicitud)
    
    return solicitud


async def completar_servicio(
    db: AsyncSession,
    id_servicio: int,
    id_taller: int
) -> Servicio:
    """
    Marca un servicio como completado y libera recursos (técnicos y vehículos)
    """
    servicio = await servicio_crud.get(db, id_servicio)
    if not servicio:
        raise ValueError("Servicio no encontrado")
    
    if servicio.id_taller != id_taller:
        raise ValueError("El servicio no pertenece a este taller")
    
    # Liberar técnicos
    tecnicos_asignados = await servicio_tecnico_crud.get_by_servicio(db, id_servicio)
    for asignacion in tecnicos_asignados:
        empleado = await empleado_crud.get(db, asignacion.id_empleado)
        if empleado:
            empleado.estado = EstadoEmpleado.disponible
    
    # Liberar vehículos
    vehiculos_asignados = await servicio_vehiculo_crud.get_by_servicio(db, id_servicio)
    for asignacion in vehiculos_asignados:
        result = await db.execute(
            select(VehiculoTaller).where(VehiculoTaller.id == asignacion.id_vehiculo_taller)
        )
        vehiculo = result.scalar_one_or_none()
        if vehiculo:
            vehiculo.estado = EstadoVehiculoTaller.disponible
    
    # Actualizar estado del servicio
    await servicio_crud.update_estado(db, id_servicio, EstadoServicio.finalizado)
    
    await db.commit()
    await db.refresh(servicio)
    
    return servicio
