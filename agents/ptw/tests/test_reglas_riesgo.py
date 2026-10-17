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
from contracts.modelos import FirmaSupervisor, PropuestaSupervisor

MOCKS = Path(__file__).resolve().parents[3] / "contracts" / "mocks"
LIMITES = TablaSheets("limites_area").filas()
CONTROLES = TablaSheets("controles_iperc").filas()


def _mock(nombre: str) -> dict:
    return json.loads((MOCKS / f"{nombre}.json").read_text(encoding="utf-8"))


def _evaluar(solicitud=None, condiciones=None, aptitud=None, incidentes=None):
    solicitud = solicitud or _mock("ptw_solicitud")
    condiciones = condiciones if condiciones is not None else _mock("area_condiciones")
    aptitud = aptitud if aptitud is not None else _mock("gemelo_aptitud")
    incidentes = incidentes if incidentes is not None else _mock("incidentes_similares")
    senales = construir_senales(solicitud, "perforacion", condiciones, aptitud, incidentes)
    evaluacion = calcular_riesgo(senales, condiciones, aptitud, incidentes, LIMITES)
    return construir_propuesta(evaluacion, armar_checklist(senales, CONTROLES))


def test_caso_juan_es_ambar_autorizar_con_controles():
    propuesta = _evaluar()
    extras = " | ".join(propuesta.controles_extra).lower()

    assert propuesta.nivel == "ambar"
    assert propuesta.decision == "autorizar_con_controles"
    for esperado in ("desatado", "sostenimiento", "medir gases", "pareja", "pausa activa obligatoria a las 2 h"):
        assert esperado in extras
    assert any("Último desatado 26 h" in p for p in propuesta.porque)
    assert any("3 incidentes similares" in p for p in propuesta.porque)


def test_oxigeno_bajo_es_rojo_y_no_ingresar():
    condiciones = {**_mock("area_condiciones"), "o2_pct": 19.0}
    propuesta = _evaluar(condiciones=condiciones)

    assert propuesta.nivel == "rojo"
    assert propuesta.decision == "reasignar"
    assert "No ingresar" in propuesta.alternativa
    assert any("art. 246" in p for p in propuesta.porque)


def test_trabajador_no_apto_es_rojo_y_reasignar():
    aptitud = {**_mock("gemelo_aptitud"), "apto_para_tarea": "no_apto", "motivo_visible": "Descanso insuficiente"}
    propuesta = _evaluar(aptitud=aptitud)

    assert propuesta.nivel == "rojo"
    assert "Reasignar la tarea a otro trabajador" in propuesta.alternativa


def test_agente_caido_nunca_baja_el_nivel():
    senales = construir_senales(_mock("ptw_solicitud"), "perforacion", None, None, None)
    evaluacion = calcular_riesgo(senales, None, None, None, LIMITES)

    assert evaluacion["nivel"] == "rojo"


def test_condiciones_normales_son_verde():
    condiciones = {**_mock("area_condiciones"), "ruido_dBA": 80, "ultimo_desatado_h": 2}
    aptitud = {**_mock("gemelo_aptitud"), "apto_para_tarea": "apto", "motivo_visible": "Sin observaciones"}
    incidentes = {**_mock("incidentes_similares"), "casos_similares": 1}
    propuesta = _evaluar(condiciones=condiciones, aptitud=aptitud, incidentes=incidentes)

    assert propuesta.nivel == "verde"
    assert propuesta.decision == "autorizar"


def test_supervisor_no_puede_ajustar_un_rojo():
    propuesta = PropuestaSupervisor(decision="reasignar", nivel="rojo", porque=["x"], controles_extra=[], alternativa="")
    firma = FirmaSupervisor(accion="ajustar", supervisor="Ing. Quispe", controles_finales=["Medir gases"])

    assert validar_firma(propuesta, firma) is not None
