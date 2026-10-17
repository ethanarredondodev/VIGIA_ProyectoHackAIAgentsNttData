import json
from pathlib import Path

from agents.comun.sheets import TablaSheets
from agents.ptw.reglas_riesgo import (
    armar_checklist,
    calcular_riesgo,
    construir_propuesta,
    construir_senales,
    validar_firma,
)
from contracts.modelos import FirmaSupervisor

MOCKS = Path(__file__).resolve().parents[3] / "contracts" / "mocks"
LIMITES = TablaSheets("limites_area").filas()
CONTROLES = TablaSheets("controles_iperc").filas()


def _mock(nombre: str) -> dict:
    return json.loads((MOCKS / f"{nombre}.json").read_text(encoding="utf-8"))


def _evaluar(solicitud=None, condiciones=None, aptitud=None, incidentes=None, tipo_tarea="perforacion"):
    solicitud = solicitud or _mock("ptw_solicitud")
    condiciones = condiciones if condiciones is not None else _mock("area_condiciones")
    aptitud = aptitud if aptitud is not None else _mock("gemelo_aptitud")
    incidentes = incidentes if incidentes is not None else _mock("incidentes_similares")
    senales = construir_senales(solicitud, tipo_tarea, condiciones, aptitud, incidentes)
    evaluacion = calcular_riesgo(senales, condiciones, aptitud, incidentes, LIMITES)
    return construir_propuesta(evaluacion, armar_checklist(senales, CONTROLES))


CONDICIONES_BUENAS = {"ruido_dBA": 80, "ultimo_desatado_h": 2}
APTO = {"apto_para_tarea": "apto", "motivo_visible": "Sin observaciones"}


def test_caso_juan_es_ambar_autorizar_con_controles():
    propuesta = _evaluar()
    extras = " | ".join(propuesta.controles_extra).lower()

    assert propuesta.nivel == "ambar"
    assert propuesta.decision == "autorizar_con_controles"
    assert propuesta.requiere_supervisor is False
    for esperado in ("desatado", "sostenimiento", "medir gases", "pareja", "pausa activa obligatoria a las 2 h"):
        assert esperado in extras
    assert any("Último desatado 26 h" in p for p in propuesta.porque)
    assert any("3 incidentes similares" in p for p in propuesta.porque)


def test_oxigeno_bajo_y_sin_ventilacion_es_rojo_y_esperar():
    condiciones = {**_mock("area_condiciones"), "o2_pct": 18.2, "ventilacion": "inoperativa"}
    propuesta = _evaluar(condiciones=condiciones)

    assert propuesta.nivel == "rojo"
    assert propuesta.decision == "reasignar"
    assert propuesta.alternativa.startswith("Esperar")
    assert any("art. 246" in p for p in propuesta.porque)


def test_trabajador_no_apto_es_rojo_y_reasignar():
    aptitud = {**_mock("gemelo_aptitud"), "apto_para_tarea": "no_apto", "motivo_visible": "Descanso insuficiente"}
    propuesta = _evaluar(aptitud=aptitud)

    assert propuesta.nivel == "rojo"
    assert "Reasignar la tarea a otro trabajador" in propuesta.alternativa


def test_agente_caido_nunca_baja_el_nivel():
    senales = construir_senales(_mock("ptw_solicitud"), "perforacion", None, None, None)
    assert calcular_riesgo(senales, None, None, None, LIMITES)["nivel"] == "rojo"


def test_condiciones_normales_son_verde_sin_supervisor():
    propuesta = _evaluar(
        condiciones={**_mock("area_condiciones"), **CONDICIONES_BUENAS},
        aptitud={**_mock("gemelo_aptitud"), **APTO},
        incidentes={**_mock("incidentes_similares"), "casos_similares": 1},
    )

    assert (propuesta.nivel, propuesta.decision, propuesta.requiere_supervisor) == ("verde", "autorizar", False)


def test_trabajo_de_alto_riesgo_requiere_supervisor_aunque_sea_verde():
    propuesta = _evaluar(
        solicitud={**_mock("ptw_solicitud"), "tarea": "trabajo en altura en chimenea"},
        condiciones={**_mock("area_condiciones"), **CONDICIONES_BUENAS},
        aptitud={**_mock("gemelo_aptitud"), **APTO},
        incidentes={**_mock("incidentes_similares"), "casos_similares": 0},
        tipo_tarea="trabajo_en_altura",
    )

    assert propuesta.nivel == "verde"
    assert propuesta.requiere_supervisor is True


def test_ajustar_exige_controles_finales():
    assert validar_firma(FirmaSupervisor(accion="ajustar", supervisor="Ing. Quispe")) is not None
    assert validar_firma(FirmaSupervisor(accion="aceptar", supervisor="Ing. Quispe")) is None
