from app.models.persona import Persona
from app.models.usuario import Usuario
from app.models.rol import Rol
from app.models.rol_usuario import RolUsuario
from app.models.dispositivo_usuario import DispositivoUsuario
from app.models.sesion import Sesion 
from app.models.vehiculo import Vehiculo
from app.models.permiso import Permiso
from app.models.rol_permiso import RolPermiso
from app.models.taller import Taller
from app.models.solicitud_afiliacion import SolicitudAfiliacion
from app.models.empleado import Empleado, EstadoEmpleado
from app.models.especialidad import Especialidad
from app.models.tecnico_especialidad import TecnicoEspecialidad
from app.models.vehiculo_taller import VehiculoTaller, TipoVehiculoTaller, EstadoVehiculoTaller
from app.models.solicitud_diagnostico import SolicitudDiagnostico
from app.models.categoria_incidente import CategoriaIncidente
from app.models.tipo_incidente import TipoIncidente
from app.models.incidente import Incidente
from app.models.evidencia import Evidencia
from app.models.diagnostico import Diagnostico
from app.models.configuracion_sistema import ConfiguracionSistema
from app.models.requiere_especialidad import RequiereEspecialidad
from app.models.solicitud_servicio import SolicitudServicio
from app.models.servicio import Servicio
from app.models.servicio_tecnico import ServicioTecnico
from app.models.servicio_vehiculo import ServicioVehiculo
from app.models.metrica import Metrica
from app.models.historial_estado_servicio import HistorialEstadoServicio
from app.models.empleado_ubicacion import EmpleadoUbicacion
from app.models.valoracion import Valoracion
from app.models.mensaje import Mensaje
from app.models.factura import Factura, EstadoPago
from app.models.bitacora_acceso import BitacoraAcceso, AccionAcceso
from app.models.ubicacion_tecnico import UbicacionTecnico