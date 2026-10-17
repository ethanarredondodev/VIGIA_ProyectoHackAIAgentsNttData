import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents.ptw.app import app

MOCKS = Path(__file__).resolve().parents[3] / "contracts" / "mocks"


def _mock(nombre: str) -> dict:
    return json.loads((MOCKS / f"{nombre}.json").read_text(encoding="utf-8"))


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    with TestClient(app) as c:
        yield c


def test_juan_de_punta_a_punta(cliente):
    petar = cliente.post("/ptw/solicitud", json=_mock("ptw_solicitud")).json()

    assert petar["estado"] == "pendiente_firma"
    assert petar["propuesta"]["nivel"] == "ambar"
    assert petar["propuesta"]["decision"] == "autorizar_con_controles"
    assert petar["insumos"]["aptitud"]["diagnostico"] is None
    assert petar["explicacion"].startswith("Nivel AMBAR")
    assert [p["id"] for p in cliente.get("/ptw", params={"estado": "pendiente_firma"}).json()] == [petar["id"]]

    firmado = cliente.post(f"/ptw/{petar['id']}/firma", json=_mock("firma")).json()
    assert firmado["estado"] == "autorizado"
    assert len(firmado["firma"]["controles_finales"]) == len(petar["checklist"])

    cerrado = cliente.post(f"/ptw/{petar['id']}/resultado", json=_mock("resultado")).json()
    assert cerrado["estado"] == "cerrado"
    assert cliente.get(f"/ptw/{petar['id']}").json()["resultado"]["controles_cumplidos"] is True


def test_incidente_vuelve_al_historial(cliente):
    petar = cliente.post("/ptw/solicitud", json=_mock("ptw_solicitud")).json()
    cliente.post(f"/ptw/{petar['id']}/firma", json=_mock("firma"))
    cliente.post(
        f"/ptw/{petar['id']}/resultado",
        json={"resultado": "casi_incidente", "controles_cumplidos": True, "observacion": "Cayó roca menor."},
    )

    registrado = app.state.clientes.registrados[-1]
    assert registrado.petar_id == petar["id"]
    assert registrado.riesgo_critico == "desprendimiento_de_roca"


def test_rechazo_termina_el_flujo(cliente):
    petar = cliente.post("/ptw/solicitud", json=_mock("ptw_solicitud")).json()
    rechazado = cliente.post(
        f"/ptw/{petar['id']}/firma", json={"accion": "rechazar", "supervisor": "Ing. Quispe"}
    ).json()

    assert rechazado["estado"] == "rechazado"
    assert cliente.post(f"/ptw/{petar['id']}/resultado", json=_mock("resultado")).status_code == 409


def test_firma_sin_supervisor_es_invalida(cliente):
    petar = cliente.post("/ptw/solicitud", json=_mock("ptw_solicitud")).json()
    assert cliente.post(f"/ptw/{petar['id']}/firma", json={"accion": "aceptar", "supervisor": ""}).status_code == 422
