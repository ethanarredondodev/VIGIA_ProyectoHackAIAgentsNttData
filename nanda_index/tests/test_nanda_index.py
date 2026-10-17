import base64
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from contracts.agent_facts import (
    SSO,
    AgentFacts,
    Endpoints,
    Habilidad,
    Proveedor,
    clave_dev,
    clave_publica_b64,
    emitir,
    firmar,
    firmar_revocaciones,
    nueva_credencial,
)
from nanda_index import app as modulo


def _ficha(autoridad: Ed25519PrivateKey | None = None, url: str = "http://area:8000"):
    clave = Ed25519PrivateKey.generate()
    credencial = emitir(nueva_credencial("vigia-area", clave_publica_b64(clave), {}, 1), {SSO: autoridad or clave_dev(SSO)})
    ahora = datetime.now(timezone.utc)
    facts = AgentFacts(
        id="vigia-area",
        agent_name="Agente de area",
        label="Vigía",
        description="Condiciones de la labor",
        version="0.1.0",
        provider=Proveedor(name="Vigía"),
        endpoints=Endpoints(static=[url]),
        skills=[Habilidad(id="condiciones", description="Gases, O2, ruido")],
        issued_at=ahora.isoformat(),
        expires_at=(ahora + timedelta(minutes=10)).isoformat(),
    )
    return firmar(facts, clave, credencial).model_dump(mode="json")


def _cliente() -> TestClient:
    modulo.indice = modulo.IndiceLocal()
    modulo.revocaciones = None
    return TestClient(modulo.app)


def test_registra_y_resuelve_agente_certificado():
    cliente = _cliente()
    ficha = _ficha()

    assert cliente.post("/register", json=ficha).status_code == 201
    resuelto = cliente.get("/resolve/vigia-area")

    assert resuelto.status_code == 200
    assert resuelto.json()["facts"]["endpoints"]["static"] == ["http://area:8000"]
    assert resuelto.json()["firma"] == ficha["firma"]


def test_rechaza_ficha_alterada():
    cliente = _cliente()
    alterada = _ficha()
    alterada["facts"]["endpoints"]["static"] = ["http://atacante:8000"]

    respuesta = cliente.post("/register", json=alterada)
    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "firma de la ficha inválida"


def test_suplantador_no_se_registra_aunque_llegue_primero():
    cliente = _cliente()
    impostor = _ficha(autoridad=Ed25519PrivateKey.generate(), url="http://atacante:8000")

    assert cliente.post("/register", json=impostor).status_code == 403
    assert cliente.post("/register", json=_ficha()).status_code == 201
    assert cliente.get("/resolve/vigia-area").json()["facts"]["endpoints"]["static"] == ["http://area:8000"]


def test_resolver_inexistente_devuelve_404():
    assert _cliente().get("/resolve/no-existe").status_code == 404


def test_clave_publica_es_ed25519_cruda():
    assert len(base64.b64decode(_ficha()["clave_publica"])) == 32


def test_revocacion_firmada_oculta_al_agente_y_bloquea_su_registro():
    cliente = _cliente()
    cliente.post("/register", json=_ficha())
    lista = firmar_revocaciones(["vigia-area"], clave_dev(SSO)).model_dump(mode="json")

    assert cliente.post("/revocaciones", json=lista).status_code == 201
    assert cliente.get("/revocaciones").json() == lista
    assert cliente.get("/resolve/vigia-area").status_code == 404
    assert cliente.post("/register", json=_ficha()).status_code == 403


def test_revocacion_sin_firma_de_la_autoridad_se_rechaza():
    lista = firmar_revocaciones(["vigia-area"], Ed25519PrivateKey.generate()).model_dump(mode="json")
    assert _cliente().post("/revocaciones", json=lista).status_code == 403


def test_no_se_puede_reponer_una_lista_anterior():
    cliente = _cliente()
    anterior = firmar_revocaciones([], clave_dev(SSO)).model_dump(mode="json")
    vigente = firmar_revocaciones(["vigia-area"], clave_dev(SSO)).model_dump(mode="json")

    cliente.post("/revocaciones", json=vigente)
    assert cliente.post("/revocaciones", json=anterior).status_code == 409
    assert cliente.get("/revocaciones").json() == vigente
