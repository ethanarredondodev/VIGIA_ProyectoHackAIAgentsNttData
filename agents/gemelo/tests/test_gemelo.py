import json
from pathlib import Path

from fastapi.testclient import TestClient

from agents.gemelo.app import app

MOCKS = Path(__file__).resolve().parents[3] / "contracts" / "mocks"
CONSULTA_JUAN = {
    "trabajador_id": "T-001",
    "tipo_tarea": "perforacion",
    "turno": "noche",
    "altitud_msnm": 4210,
    "tipo_mineria": "subterranea",
    "empleador": "contratista",
}


def _aptitud(consulta: dict) -> dict:
    with TestClient(app) as cliente:
        respuesta = cliente.post("/gemelo/aptitud", json=consulta)
    assert respuesta.status_code == 200
    return respuesta.json()


def test_juan_apto_con_observaciones_igual_al_mock():
    mock = json.loads((MOCKS / "gemelo_aptitud.json").read_text(encoding="utf-8"))
    assert _aptitud(CONSULTA_JUAN) == mock


def test_nunca_expone_detalle_clinico():
    cuerpo = _aptitud(CONSULTA_JUAN)
    texto = json.dumps(cuerpo, ensure_ascii=False).lower()

    assert set(cuerpo) == {"trabajador_id", "apto_para_tarea", "motivo_visible", "diagnostico"}
    assert cuerpo["diagnostico"] is None
    for dato_privado in ("hipoacusia", "5.1", "sueno", "datos_clinicos", "emo_vigente"):
        assert dato_privado not in texto


def test_poco_sueno_es_no_apto_y_solo_muestra_el_motivo_mas_grave():
    cuerpo = _aptitud({**CONSULTA_JUAN, "trabajador_id": "T-003", "tipo_tarea": "desatado"})

    assert cuerpo["apto_para_tarea"] == "no_apto"
    assert ";" not in cuerpo["motivo_visible"]


def test_trabajador_descansado_es_apto():
    cuerpo = _aptitud({**CONSULTA_JUAN, "trabajador_id": "T-002", "altitud_msnm": 3400,
                       "tipo_mineria": "tajo_abierto", "turno": "dia", "tipo_tarea": "carguio"})
    assert cuerpo["apto_para_tarea"] == "apto"


def test_trabajador_sin_gemelo_no_es_apto():
    assert _aptitud({**CONSULTA_JUAN, "trabajador_id": "T-999"})["apto_para_tarea"] == "no_apto"


def test_no_hay_endpoints_de_detalle():
    assert {r.path for r in app.routes} == {"/gemelo/aptitud", "/health", "/.well-known/agent-facts"}
