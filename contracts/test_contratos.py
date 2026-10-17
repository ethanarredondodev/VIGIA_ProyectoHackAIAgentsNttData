import json
from pathlib import Path

from contracts.exportar_schemas import DIRECTORIO, schemas
from contracts.modelos import (
    FirmaSupervisor,
    RespuestaAptitud,
    RespuestaArea,
    RespuestaIncidentes,
    ResultadoTarea,
    SolicitudPTW,
)
from contracts.vocabulario import clasificar_labor, clasificar_tarea

MOCKS = Path(__file__).parent / "mocks"


def test_mocks_cumplen_los_contratos():
    pares = {
        "ptw_solicitud": SolicitudPTW,
        "incidentes_similares": RespuestaIncidentes,
        "area_condiciones": RespuestaArea,
        "gemelo_aptitud": RespuestaAptitud,
        "firma": FirmaSupervisor,
        "resultado": ResultadoTarea,
    }
    for nombre, modelo in pares.items():
        modelo.model_validate(json.loads((MOCKS / f"{nombre}.json").read_text(encoding="utf-8")))


def test_gemelo_no_acepta_diagnostico():
    try:
        RespuestaAptitud(trabajador_id="T-001", apto_para_tarea="apto", motivo_visible="", diagnostico="x")
    except ValueError:
        return
    raise AssertionError("diagnostico debe ser siempre null")


def test_schemas_json_estan_al_dia():
    for nombre, contenido in schemas().items():
        assert (DIRECTORIO / f"{nombre}.json").read_text(encoding="utf-8") == contenido, (
            f"Ejecuta: python -m contracts.exportar_schemas ({nombre} desactualizado)"
        )


def test_vocabulario_del_caso_juan():
    assert clasificar_tarea("perforación de frente") == "perforacion"
    assert clasificar_labor("perforación de frente", "NV-3820 TJ-12") == "frente_avance"
    assert clasificar_labor("desatado de rocas", "NV-3900 GA-05") == "galeria"
