import json
from pathlib import Path

from fastapi.testclient import TestClient

from agents.area.app import app

MOCKS = Path(__file__).resolve().parents[3] / "contracts" / "mocks"
DATOS = Path(__file__).resolve().parents[3] / "data" / "synthetic"


def _leer(nombre: str):
    return json.loads((DATOS / f"{nombre}.json").read_text(encoding="utf-8"))


def test_clima_del_yacimiento_viene_de_la_planilla():
    clima = _leer("clima")
    dia_de_la_crisis = next(c for c in clima if c["fecha"] == "2026-09-02")

    assert [c["clima_id"] for c in clima] == list(range(1, 17))
    assert len({c["fecha"] for c in clima}) == 16
    assert (dia_de_la_crisis["tipo_clima"], dia_de_la_crisis["velocidad_viento_kmh"]) == ("Frío y ventoso", 28.0)


def test_labores_traen_su_ficha_geotecnica():
    labores = {lab["labor"]: lab for lab in _leer("labores")}

    assert all(lab["nombre"] and lab["tipo"] and lab["riesgo_geotecnico"] in ("bajo", "medio", "alto")
               and lab["ultima_inspeccion"] for lab in labores.values())
    assert labores["TA-FASE4 BC-3400"]["angulo_talud"] == 38.0
    assert labores["NV-3820 TJ-12"]["angulo_talud"] is None
    assert (labores["NV-3820 GA-07"]["nombre"], labores["NV-3820 GA-07"]["ultima_inspeccion"]) == (
        "Nivel 3, galería de perforación (3,800 msnm)", "2026-09-28",
    )


def test_condiciones_de_la_labor_de_juan_coinciden_con_el_mock():
    mock = json.loads((MOCKS / "area_condiciones.json").read_text(encoding="utf-8"))
    with TestClient(app) as cliente:
        respuesta = cliente.post("/area/condiciones", json={"labor": "NV-3820 TJ-12"})

    assert respuesta.status_code == 200
    assert respuesta.json() == mock


def test_labor_desconocida_devuelve_404():
    with TestClient(app) as cliente:
        assert cliente.post("/area/condiciones", json={"labor": "NV-0000 XX-00"}).status_code == 404


def test_expone_agent_facts_firmadas():
    with TestClient(app) as cliente:
        facts = cliente.get("/.well-known/agent-facts").json()

    assert facts["facts"]["id"] == "vigia-area"
    assert facts["algoritmo"] == "Ed25519"
