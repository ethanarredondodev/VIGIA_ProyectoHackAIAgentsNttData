import json
from pathlib import Path

from fastapi.testclient import TestClient

from agents.incidentes.app import app
from contracts.modelos import RespuestaIncidentes

MOCKS = Path(__file__).resolve().parents[3] / "contracts" / "mocks"
CONSULTA_JUAN = {
    "tarea": "perforación de frente",
    "tipo_tarea": "perforacion",
    "labor": "NV-3820 TJ-12",
    "turno": "noche",
    "tipo_mineria": "subterranea",
}


def test_caso_juan_devuelve_tres_incidentes_de_desprendimiento():
    with TestClient(app) as cliente:
        respuesta = cliente.post("/incidentes/similares", json=CONSULTA_JUAN)

    cuerpo = RespuestaIncidentes.model_validate(respuesta.json())
    assert cuerpo.casos_similares == 3
    assert cuerpo.riesgo_potencial_max == "alto"
    assert {c.id for c in cuerpo.casos} == {"INC-0007", "INC-0012", "INC-0019"}
    assert all(c.riesgo_critico == "desprendimiento_de_roca" for c in cuerpo.casos)
    assert "desprendimiento de roca" in cuerpo.patron


def test_relaja_turno_si_hay_pocos_casos():
    consulta = {**CONSULTA_JUAN, "tarea": "carguío de mineral con pala", "tipo_tarea": "carguio",
                "labor": "TA-FASE4 BC-3400", "turno": "noche", "tipo_mineria": "tajo_abierto"}
    with TestClient(app) as cliente:
        cuerpo = cliente.post("/incidentes/similares", json=consulta).json()

    assert cuerpo["casos_similares"] == 1
    assert cuerpo["riesgo_potencial_max"] == "medio"


def test_sin_casos_devuelve_ninguno():
    consulta = {**CONSULTA_JUAN, "tarea": "izaje de materiales", "tipo_tarea": "izaje", "labor": "NV-1 GA-01"}
    with TestClient(app) as cliente:
        cuerpo = cliente.post("/incidentes/similares", json=consulta).json()

    assert cuerpo == {"casos_similares": 0, "patron": "Sin incidentes similares registrados.",
                      "riesgo_potencial_max": "ninguno", "casos": []}


def test_resultado_con_novedad_vuelve_al_historial():
    registro = {
        "petar_id": "PTW-TEST01", "tipo_tarea": "perforacion", "labor": "NV-3820 TJ-12",
        "tarea": "perforación de frente", "turno": "noche", "tipo_mineria": "subterranea",
        "riesgo_critico": "desprendimiento_de_roca", "potencial": "alto",
        "resumen_es": "Caída de roca menor durante la perforación.",
    }
    with TestClient(app) as cliente:
        assert cliente.post("/incidentes/registrar", json=registro).status_code == 201
        cuerpo = cliente.post("/incidentes/similares", json=CONSULTA_JUAN).json()

    assert cuerpo["casos_similares"] == 4


def test_respuesta_coincide_con_el_mock_del_contrato():
    mock = json.loads((MOCKS / "incidentes_similares.json").read_text(encoding="utf-8"))
    with TestClient(app) as cliente:
        cuerpo = cliente.post("/incidentes/similares", json=CONSULTA_JUAN).json()

    assert set(cuerpo) == set(mock)
    assert sorted(c["id"] for c in cuerpo["casos"]) == sorted(c["id"] for c in mock["casos"])
