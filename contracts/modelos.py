"""Contratos JSON de Vigía. Estan fijados: ningun servicio los cambia.

Cada modelo se exporta a JSON Schema en contracts/schemas/ con
`python -m contracts.exportar_schemas`.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoMineria = Literal["subterranea", "tajo_abierto"]
Turno = Literal["dia", "noche"]
Empleador = Literal["titular", "contratista"]
Aptitud = Literal["apto", "apto_con_observaciones", "no_apto"]
Potencial = Literal["ninguno", "bajo", "medio", "alto", "critico"]
Ventilacion = Literal["operativa", "deficiente", "inoperativa", "natural"]
Decision = Literal["autorizar", "autorizar_con_controles", "reasignar"]
Nivel = Literal["verde", "ambar", "rojo"]
AccionFirma = Literal["aceptar", "ajustar", "rechazar"]
Resultado = Literal["sin_novedad", "casi_incidente", "incidente"]
NivelExposicion = Literal["baja", "media", "alta"]
EstadoPtw = Literal[
    "procesando", "emitido", "en_revision", "bloqueado",
    "autorizado_con_controles", "rechazado", "en_ejecucion", "cerrado",
]


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- PTW -------------------------------------------------------------------

class SolicitudPTW(Contrato):
    """POST /ptw/solicitud"""

    tarea: str = Field(min_length=3)
    labor: str = Field(min_length=2)
    turno: Turno
    trabajador_id: str = Field(min_length=1)
    altitud_msnm: int = Field(ge=0, le=6500)
    tipo_mineria: TipoMineria
    empleador: Empleador


class SolicitudAceptada(Contrato):
    """Respuesta de POST /ptw/solicitud: la evaluacion sigue en segundo plano."""

    ptw_id: str
    estado: Literal["procesando"] = "procesando"


class PropuestaSupervisor(Contrato):
    """Propuesta calculada por reglas. requiere_supervisor = algun control aplicable es de alto riesgo."""

    decision: Decision
    nivel: Nivel
    requiere_supervisor: bool
    porque: list[str]
    controles_extra: list[str]
    alternativa: str


class FirmaSupervisor(Contrato):
    """POST /ptw/{id}/firma"""

    accion: AccionFirma
    supervisor: str = Field(min_length=1)
    controles_finales: list[str] = []


class ResultadoTarea(Contrato):
    """POST /ptw/{id}/resultado"""

    resultado: Resultado
    controles_cumplidos: bool
    observacion: str = ""


class ItemChecklist(Contrato):
    """Detalle interno de cada control del checklist IPERC (se guarda para auditoria)."""

    id: str
    control: str
    riesgo_critico: str
    trabajo_alto_riesgo: bool
    jerarquia: str
    base_legal: str
    origen: Literal["base", "extra"]


class EvidenciaFirma(Contrato):
    """Prueba de que el agente certificado emitio la respuesta: Ed25519 sobre `nonce` y el sha256 del cuerpo."""

    nonce: str
    sha256: str
    firma: str
    clave_publica: str


class EstadoConsulta(Contrato):
    estado: Literal["pendiente", "ok", "error"]
    data: dict | None = None
    evidencia: EvidenciaFirma | None = None


class Consultas(Contrato):
    incidentes: EstadoConsulta
    area: EstadoConsulta
    gemelo: EstadoConsulta


class AgenteNanda(Contrato):
    """`firma` es `valida` solo si la credencial de las autoridades es vigente, no esta revocada y la ficha cuadra."""

    id: str
    capabilities: list[str]
    firma: Literal["valida", "invalida"]
    emisores: list[str] = []
    credencial_vence: datetime | None = None
    motivo: str | None = None


class PetarEmitido(Contrato):
    numero: str
    checklist: list[str]
    firmado_por: str | None
    emitido_en: datetime


class Ptw(Contrato):
    """GET /ptw/{id}. `consultas` se actualiza a medida que responde cada agente."""

    ptw_id: str
    estado: EstadoPtw
    solicitud: SolicitudPTW
    consultas: Consultas
    nanda: list[AgenteNanda]
    propuesta: PropuestaSupervisor | None = None
    petar: PetarEmitido | None = None
    explicacion: str | None = None


class ItemBandeja(Contrato):
    """GET /ptw/bandeja: revision = ambar o alto riesgo; aviso = rojo. Los verdes no aparecen."""

    ptw_id: str
    nivel: Nivel
    requiere_supervisor: bool
    trabajador_nombre: str
    tarea: str
    labor: str
    turno: Turno
    creado_en: datetime
    tipo: Literal["revision", "aviso"]


# --- Incidentes ------------------------------------------------------------

class ConsultaIncidentes(Contrato):
    tarea: str
    tipo_tarea: str
    labor: str
    turno: Turno
    tipo_mineria: TipoMineria


class CasoIncidente(Contrato):
    id: str
    resumen_es: str
    riesgo_critico: str
    causa_probable: str


class RespuestaIncidentes(Contrato):
    """POST /incidentes/similares"""

    casos_similares: int = Field(ge=0)
    patron: str
    riesgo_potencial_max: Potencial
    casos: list[CasoIncidente]


class RegistroIncidente(Contrato):
    """POST /incidentes/registrar: el resultado de una tarea vuelve al historial."""

    petar_id: str
    tipo_tarea: str
    labor: str
    tarea: str
    turno: Turno
    tipo_mineria: TipoMineria
    riesgo_critico: str
    potencial: Literal["bajo", "medio", "alto", "critico"]
    resumen_es: str


# --- Area ------------------------------------------------------------------

class ConsultaArea(Contrato):
    labor: str


class RespuestaArea(Contrato):
    """POST /area/condiciones"""

    labor: str
    co_ppm: float = Field(ge=0)
    o2_pct: float = Field(ge=0, le=100)
    ventilacion: Ventilacion
    ruido_dBA: float = Field(ge=0)
    ultimo_desatado_h: float = Field(ge=0)


# --- Gemelo (zona clinica) -------------------------------------------------

class ConsultaAptitud(Contrato):
    trabajador_id: str
    tipo_tarea: str
    turno: Turno
    altitud_msnm: int
    tipo_mineria: TipoMineria
    empleador: Empleador


class RespuestaAptitud(Contrato):
    """POST /gemelo/aptitud. Nunca contiene detalle clinico: `diagnostico` es siempre null."""

    trabajador_id: str
    apto_para_tarea: Aptitud
    motivo_visible: str
    diagnostico: None = None


class EstadoVisual(Contrato):
    apto_para_tarea: Aptitud
    motivo_visible: str
    energia: int = Field(ge=0, le=100)
    dia_rotacion: int
    total_rotacion: int
    exposicion_nivel: NivelExposicion
    historial_energia: list[int] = Field(min_length=14, max_length=14)


class AvatarGemelo(Contrato):
    """GET /gemelo/{id}/avatar y GET /trabajadores/{id}/avatar. Sin datos clinicos ni fotos."""

    trabajador_id: str
    nombre: str
    cargo: str
    empresa: str
    empleador: Empleador
    seed: str
    color_casco: str
    estado_visual: EstadoVisual


CONTRATOS = [
    SolicitudPTW,
    SolicitudAceptada,
    PropuestaSupervisor,
    FirmaSupervisor,
    ResultadoTarea,
    ItemChecklist,
    Ptw,
    ItemBandeja,
    ConsultaIncidentes,
    RespuestaIncidentes,
    RegistroIncidente,
    ConsultaArea,
    RespuestaArea,
    ConsultaAptitud,
    RespuestaAptitud,
    AvatarGemelo,
]
