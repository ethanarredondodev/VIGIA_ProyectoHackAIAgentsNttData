import json
from pathlib import Path

from fastapi.testclient import TestClient

from agents.area.app import app

MOCKS = Path(__file__).resolve().parents[3] / "contracts" / "mocks"


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
