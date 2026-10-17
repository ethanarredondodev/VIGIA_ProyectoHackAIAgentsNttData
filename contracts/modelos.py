"""Contratos JSON de Vigia. Estan fijados: ningun servicio los cambia.

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
EstadoPetar = Literal["evaluando", "pendiente_firma", "autorizado", "reasignado", "rechazado", "cerrado"]


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


class PropuestaSupervisor(Contrato):
    """Propuesta que el orquestador entrega al supervisor."""

    decision: Decision
    nivel: Nivel
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
    id: str
    control: str
    riesgo_critico: str
    jerarquia: str
    base_legal: str
    origen: Literal["base", "extra"]


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


# --- Registro PETAR (lectura) ----------------------------------------------

class Insumos(Contrato):
    incidentes: RespuestaIncidentes | None = None
    condiciones: RespuestaArea | None = None
    aptitud: RespuestaAptitud | None = None


class Petar(Contrato):
    id: str
    estado: EstadoPetar
    solicitud: SolicitudPTW
    propuesta: PropuestaSupervisor | None = None
    checklist: list[ItemChecklist] = []
    explicacion: str = ""
    insumos: Insumos = Insumos()
    errores: list[str] = []
    firma: FirmaSupervisor | None = None
    resultado: ResultadoTarea | None = None
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None


CONTRATOS = [
    SolicitudPTW,
    PropuestaSupervisor,
    FirmaSupervisor,
    ResultadoTarea,
    ItemChecklist,
    ConsultaIncidentes,
    RespuestaIncidentes,
    RegistroIncidente,
    ConsultaArea,
    RespuestaArea,
    ConsultaAptitud,
    RespuestaAptitud,
    Petar,
]
