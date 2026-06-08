from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core import deps
from app.models.usuario import Usuario
from app.models.taller import Taller
from app.models.servicio import Servicio, EstadoServicio
from app.models.solicitud_servicio import SolicitudServicio
from app.models.metrica import Metrica
from app.models.incidente import Incidente
from app.models.tipo_incidente import TipoIncidente
from app.models.diagnostico import Diagnostico
from geoalchemy2.functions import ST_X, ST_Y

router = APIRouter()

@router.get("/taller/{taller_id}/kpis")
async def get_kpis(
    taller_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: Usuario = Depends(deps.get_current_active_user)
):
    # Validar permisos
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    taller = await db.scalar(select(Taller).where(Taller.id == taller_id, Taller.tenant_id == current_user.tenant_id))
    if not taller:
        raise HTTPException(status_code=404, detail="Taller no encontrado o sin acceso")

    # 1. Tiempo promedio de asignación (en Metrica)
    query_asignacion = select(func.avg(Metrica.tiempo_respuesta)).join(Servicio).where(Servicio.id_taller == taller_id)
    avg_asignacion = await db.scalar(query_asignacion)
    avg_asignacion_min = avg_asignacion.total_seconds() / 60 if avg_asignacion else 0

    # 2. Tiempo promedio de llegada
    query_llegada = select(func.avg(Metrica.tiempo_llegada)).join(Servicio).where(Servicio.id_taller == taller_id)
    avg_llegada = await db.scalar(query_llegada)
    avg_llegada_min = avg_llegada.total_seconds() / 60 if avg_llegada else 0

    # 3. Incidentes por tipo
    query_tipos = (
        select(TipoIncidente.nombre, func.count(Incidente.id_tipo_incidente))
        .join(Incidente.tipo_incidente)
        .join(Diagnostico, Diagnostico.id == Incidente.id_diagnostico)
        .join(SolicitudServicio, SolicitudServicio.id_diagnostico == Diagnostico.id)
        .where(SolicitudServicio.id_taller == taller_id)
        .group_by(TipoIncidente.nombre)
    )
    result_tipos = await db.execute(query_tipos)
    incidentes_por_tipo = [{"tipo": row[0], "cantidad": row[1]} for row in result_tipos]

    # 4. Zonas de incidentes
    query_zonas = select(
        ST_Y(SolicitudServicio.ubicacion).label('lat'),
        ST_X(SolicitudServicio.ubicacion).label('lng')
    ).where(SolicitudServicio.id_taller == taller_id, SolicitudServicio.ubicacion != None)
    result_zonas = await db.execute(query_zonas)
    zonas = [{"lat": row.lat, "lng": row.lng, "intensidad": 1} for row in result_zonas if row.lat and row.lng]

    # 5. Casos cancelados
    query_cancelados = select(func.count(Servicio.id)).where(Servicio.id_taller == taller_id, Servicio.estado == EstadoServicio.cancelado)
    casos_cancelados = await db.scalar(query_cancelados) or 0

    # 6. Cumplimiento SLA (llegada <= 30 mins)
    # Usamos extract epoch para calcular la duración en segundos y verificar si es <= 1800 (30 minutos)
    query_sla_cumplidos = select(func.count(Metrica.id)).join(Servicio).where(
        Servicio.id_taller == taller_id,
        func.extract('epoch', Metrica.tiempo_llegada) <= 1800
    )
    query_total_metricas = select(func.count(Metrica.id)).join(Servicio).where(
        Servicio.id_taller == taller_id,
        Metrica.tiempo_llegada != None
    )
    sla_cumplidos = await db.scalar(query_sla_cumplidos) or 0
    total_metricas = await db.scalar(query_total_metricas) or 0
    porcentaje_sla = (sla_cumplidos / total_metricas * 100) if total_metricas > 0 else 100.0

    # 7. Talleres más eficientes (ranking en el tenant basado en tiempo de resolución + llegada)
    query_ranking = (
        select(Taller.id, Taller.nombre, func.avg(Metrica.tiempo_resolucion).label("avg_resolucion"))
        .join(Servicio, Servicio.id_taller == Taller.id)
        .join(Metrica, Metrica.id_servicio == Servicio.id)
        .where(Taller.tenant_id == current_user.tenant_id)
        .group_by(Taller.id)
        .order_by(func.avg(Metrica.tiempo_resolucion).asc())
    )
    result_ranking = await db.execute(query_ranking)
    ranking = []
    for row in result_ranking:
        avg_res = row.avg_resolucion
        avg_mins = avg_res.total_seconds() / 60 if avg_res else 0
        ranking.append({"taller_id": row.id, "nombre": row.nombre, "tiempo_promedio_total_minutos": round(avg_mins, 2)})

    return {
        "tiempo_promedio_asignacion_minutos": round(avg_asignacion_min, 2),
        "tiempo_promedio_llegada_minutos": round(avg_llegada_min, 2),
        "incidentes_por_tipo": incidentes_por_tipo,
        "talleres_mas_eficientes": ranking,
        "zonas_incidentes": zonas,
        "casos_cancelados": casos_cancelados,
        "nivel_cumplimiento_sla_porcentaje": round(porcentaje_sla, 2)
    }
