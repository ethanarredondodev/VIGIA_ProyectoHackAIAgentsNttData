import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from contracts.agent_facts import AgentFacts, Endpoints, Habilidad, Proveedor, firmar
from nanda_index import app as modulo


def _facts(agent_id: str = "vigia-area") -> AgentFacts:
    return AgentFacts(
        id=agent_id,
        agent_name="Agente de area",
        label="Vigia",
        description="Condiciones de la labor",
        version="0.1.0",
        provider=Proveedor(name="Vigia"),
        endpoints=Endpoints(static=["http://area:8000"]),
        skills=[Habilidad(id="condiciones", description="Gases, O2, ruido")],
        issued_at="2026-10-17T00:00:00+00:00",
    )


def _cliente() -> TestClient:
    modulo.indice = modulo.IndiceLocal()
    return TestClient(modulo.app)


def test_registra_y_resuelve_facts_firmadas():
    cliente = _cliente()
    firmadas = firmar(_facts(), Ed25519PrivateKey.generate())

    assert cliente.post("/register", json=firmadas.model_dump(mode="json")).status_code == 201
    resuelto = cliente.get("/resolve/vigia-area")

    assert resuelto.status_code == 200
    assert resuelto.json()["facts"]["endpoints"]["static"] == ["http://area:8000"]
    assert resuelto.json()["firma"] == firmadas.firma


def test_rechaza_firma_alterada():
    cliente = _cliente()
    firmadas = firmar(_facts(), Ed25519PrivateKey.generate())
    alterado = firmadas.model_dump(mode="json")
    alterado["facts"]["endpoints"]["static"] = ["http://atacante:8000"]

    assert cliente.post("/register", json=alterado).status_code == 400


def test_rechaza_cambio_de_clave_para_el_mismo_id():
    cliente = _cliente()
    primero = firmar(_facts(), Ed25519PrivateKey.generate())
    impostor = firmar(_facts(), Ed25519PrivateKey.generate())

    cliente.post("/register", json=primero.model_dump(mode="json"))
    respuesta = cliente.post("/register", json=impostor.model_dump(mode="json"))

    assert respuesta.status_code == 409
    assert cliente.get("/resolve/vigia-area").json()["clave_publica"] == primero.clave_publica


def test_resolver_inexistente_devuelve_404():
    assert _cliente().get("/resolve/no-existe").status_code == 404


def test_clave_publica_es_ed25519_cruda():
    firmadas = firmar(_facts(), Ed25519PrivateKey.generate())
    assert len(base64.b64decode(firmadas.clave_publica)) == 32
