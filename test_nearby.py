import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.services import solicitud_servicio_service

async def main():
    async with AsyncSessionLocal() as session:
        # Get all diagnostics to find a valid one
        from sqlalchemy import select
        from app.models.diagnostico import Diagnostico
        result = await session.execute(select(Diagnostico))
        diagnosticos = result.scalars().all()
        if not diagnosticos:
            print("No diagnosticos found")
            return
            
        d = diagnosticos[-1]
        print(f"Testing diagnostico ID: {d.id}")
        
        esp = await solicitud_servicio_service.obtener_especialidades_requeridas(session, d.id)
        print(f"Especialidades requeridas: {esp}")
        
        from app.models.solicitud_diagnostico import SolicitudDiagnostico
        sd = await session.get(SolicitudDiagnostico, d.id_solicitud_diagnostico)
        from geoalchemy2.shape import to_shape
        # Hardcode a location near the workshop
        ubicacion = (-17.3895, -66.1568)
        print(f"Ubicacion cliente (hardcoded): {ubicacion}")
        
        talleres = await solicitud_servicio_service.buscar_talleres_cercanos_con_especialidades(
            session, ubicacion, esp, 50.0
        )
        print(f"Talleres encontrados: {talleres}")
        
        # test without specialties requirement
        print("Testing without specialties requirement:")
        talleres_no_req = await solicitud_servicio_service.buscar_talleres_cercanos_con_especialidades(
            session, ubicacion, [], 50.0
        )
        print(f"Talleres encontrados (no req): {talleres_no_req}")

if __name__ == "__main__":
    asyncio.run(main())
