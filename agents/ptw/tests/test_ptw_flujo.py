import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from agents.comun import llm
from agents.ptw.app import app, enmascarar, montar_grafo
from agents.ptw.clientes import AgenteNoConfiable, ClientesAgentes, ClientesMock
from agents.ptw.repo import RepoPtwMemoria
from contracts.agent_facts import (
    SALUD,
    SSO,
    ZONA_CLINICA,
    AgentFacts,
    Endpoints,
    Habilidad,
    Proveedor,
    clave_dev,
    clave_publica_b64,
    emitir,
    firmar,
    firmar_respuesta,
    firmar_revocaciones,
    nueva_credencial,
)
from contracts.modelos import ConsultaAptitud, ConsultaArea, RespuestaAptitud, RespuestaArea, RespuestaIncidentes
from contracts.vocabulario import TIPOS_TAREA

MOCKS = Path(__file__).resolve().parents[3] / "contracts" / "mocks"
DATOS = Path(__file__).resolve().parents[3] / "data" / "synthetic"


def _mock(nombre: str) -> dict:
    return json.loads((MOCKS / f"{nombre}.json").read_text(encoding="utf-8"))


class ClientesEscenario(ClientesMock):
    """Mock con condiciones de la labor, aptitud e incidentes modificables."""

    def __init__(self, area: dict | None = None, gemelo: dict | None = None, incidentes: dict | None = None):
        super().__init__()
        self.cambios = {"area": area or {}, "gemelo": gemelo or {}, "incidentes": incidentes or {}}

    async def area(self, destino, consulta):
        base, evidencia = await super().area(destino, consulta)
        return RespuestaArea.model_validate({**base.model_dump(), **self.cambios["area"]}), evidencia

    async def gemelo(self, destino, consulta):
        base, evidencia = await super().gemelo(destino, consulta)
        return RespuestaAptitud.model_validate({**base.model_dump(), **self.cambios["gemelo"]}), evidencia

    async def incidentes(self, destino, consulta):
        base, evidencia = await super().incidentes(destino, consulta)
        return RespuestaIncidentes.model_validate({**base.model_dump(), **self.cambios["incidentes"]}), evidencia


class GemeloRevocado(ClientesMock):
    async def resolver(self):
        destinos, nanda = await super().resolver()
        destinos["gemelo"] = None
        for ficha in nanda:
            if ficha["id"] == "vigia-gemelo":
                ficha.update(firma="invalida", motivo="credencial revocada por la autoridad")
        return destinos, nanda


VERDE = ClientesEscenario(
    area={"ruido_dBA": 82, "ultimo_desatado_h": 2},
    gemelo={"apto_para_tarea": "apto", "motivo_visible": "Sin observaciones para la tarea"},
    incidentes={"casos_similares": 0, "riesgo_potencial_max": "ninguno", "casos": [], "patron": "Sin incidentes"},
)
ROJO = ClientesEscenario(area={"o2_pct": 18.2, "ventilacion": "inoperativa"})


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    with TestClient(app) as c:
        yield c


def _solicitar(cliente, clientes=None, solicitud=None) -> dict:
    if clientes is not None:
        montar_grafo(app, clientes, InMemorySaver())
    aceptada = cliente.post("/ptw/solicitud", json=solicitud or _mock("ptw_solicitud"))
    assert aceptada.status_code == 202
    assert aceptada.json()["estado"] == "procesando"
    return cliente.get(f"/ptw/{aceptada.json()['ptw_id']}").json()


def test_ambar_va_a_revision_y_se_cierra(cliente):
    ptw = _solicitar(cliente)

    assert ptw["estado"] == "en_revision"
    assert ptw["propuesta"]["nivel"] == "ambar"
    assert ptw["propuesta"]["requiere_supervisor"] is False
    assert {k: v["estado"] for k, v in ptw["consultas"].items()} == {"incidentes": "ok", "area": "ok", "gemelo": "ok"}
    assert ptw["consultas"]["gemelo"]["data"]["diagnostico"] is None
    assert all(a["firma"] == "valida" for a in ptw["nanda"])
    assert "petar" not in ptw
    bandeja = cliente.get("/ptw/bandeja").json()
    assert [(b["ptw_id"], b["tipo"], b["trabajador_nombre"]) for b in bandeja] == [
        (ptw["ptw_id"], "revision", "Juan Mamani")
    ]

    firmado = cliente.post(f"/ptw/{ptw['ptw_id']}/firma", json=_mock("firma")).json()
    assert firmado["estado"] == "autorizado_con_controles"
    assert firmado["petar"]["firmado_por"] == "Ing. Rosa Quispe"
    assert set(ptw["propuesta"]["controles_extra"]) <= set(firmado["petar"]["checklist"])
    assert cliente.get("/ptw/bandeja").json() == []

    assert cliente.post(f"/ptw/{ptw['ptw_id']}/inicio").json()["estado"] == "en_ejecucion"
    cerrado = cliente.post(f"/ptw/{ptw['ptw_id']}/resultado", json=_mock("resultado")).json()
    assert cerrado["estado"] == "cerrado"


def test_verde_se_emite_solo_y_no_entra_a_la_bandeja(cliente):
    ptw = _solicitar(cliente, VERDE)

    assert ptw["estado"] == "emitido"
    assert ptw["propuesta"]["nivel"] == "verde"
    assert ptw["petar"]["firmado_por"] is None
    assert ptw["petar"]["numero"].startswith("PETAR-")
    assert cliente.get("/ptw/bandeja").json() == []
    assert cliente.post(f"/ptw/{ptw['ptw_id']}/firma", json=_mock("firma")).status_code == 409
    assert cliente.post(f"/ptw/{ptw['ptw_id']}/resultado", json=_mock("resultado")).json()["estado"] == "cerrado"


def test_verde_de_alto_riesgo_va_a_firma(cliente):
    solicitud = {**_mock("ptw_solicitud"), "tarea": "trabajo en altura en chimenea"}
    ptw = _solicitar(cliente, VERDE, solicitud)

    assert ptw["propuesta"]["nivel"] == "verde"
    assert ptw["propuesta"]["requiere_supervisor"] is True
    assert ptw["estado"] == "en_revision"
    assert cliente.get("/ptw/bandeja").json()[0]["tipo"] == "revision"


def test_rojo_se_bloquea_sin_esperar_firma(cliente):
    ptw = _solicitar(cliente, ROJO)

    assert ptw["estado"] == "bloqueado"
    assert ptw["propuesta"]["nivel"] == "rojo"
    assert "petar" not in ptw
    estado_grafo = app.state.grafo.get_state({"configurable": {"thread_id": ptw["ptw_id"]}})
    assert estado_grafo.next == () and not estado_grafo.interrupts
    assert cliente.post(f"/ptw/{ptw['ptw_id']}/firma", json=_mock("firma")).status_code == 409
    assert [(b["tipo"], b["nivel"]) for b in cliente.get("/ptw/bandeja").json()] == [("aviso", "rojo")]


def test_incidente_vuelve_al_historial(cliente):
    ptw = _solicitar(cliente)
    cliente.post(f"/ptw/{ptw['ptw_id']}/firma", json=_mock("firma"))
    cliente.post(
        f"/ptw/{ptw['ptw_id']}/resultado",
        json={"resultado": "casi_incidente", "controles_cumplidos": True, "observacion": "Cayó roca menor."},
    )

    registrado = app.state.clientes.registrados[-1]
    assert registrado.petar_id == ptw["ptw_id"]
    assert registrado.riesgo_critico == "desprendimiento_de_roca"


def test_rechazo_termina_el_flujo(cliente):
    ptw = _solicitar(cliente)
    rechazado = cliente.post(f"/ptw/{ptw['ptw_id']}/firma", json={"accion": "rechazar", "supervisor": "Ing. Quispe"})

    assert rechazado.json()["estado"] == "rechazado"
    assert cliente.post(f"/ptw/{ptw['ptw_id']}/resultado", json=_mock("resultado")).status_code == 409


def test_firma_sin_supervisor_es_invalida(cliente):
    ptw = _solicitar(cliente)
    respuesta = cliente.post(f"/ptw/{ptw['ptw_id']}/firma", json={"accion": "aceptar", "supervisor": ""})
    assert respuesta.status_code == 422


def test_trabajador_no_registrado_no_pide_permiso(cliente):
    respuesta = cliente.post("/ptw/solicitud", json={**_mock("ptw_solicitud"), "trabajador_id": "T-999"})

    assert respuesta.status_code == 404
    assert cliente.get("/ptw", params={"trabajador_id": "T-999"}).json() == []


def test_trabajador_inactivo_no_pide_permiso(cliente):
    app.state.repo = RepoPtwMemoria([{
        "trabajador_id": "T-001", "nombres": "Juan", "apellidos": "Mamani", "cargo": "Perforista",
        "empresa": "Contratista Minera Sintética S.A.C.", "empleador": "contratista", "estado": "inactivo",
    }])

    assert cliente.post("/ptw/solicitud", json=_mock("ptw_solicitud")).status_code == 409


def test_bandeja_muestra_el_nombre_del_padron_aunque_el_gemelo_falle(cliente):
    ptw = _solicitar(cliente, GemeloRevocado())

    assert [(b["ptw_id"], b["trabajador_nombre"]) for b in cliente.get("/ptw/bandeja").json()] == [
        (ptw["ptw_id"], "Juan Mamani")
    ]


def test_solicitudes_de_demo_son_de_trabajadores_registrados():
    padron = {t["trabajador_id"] for t in json.loads((DATOS / "trabajadores.json").read_text(encoding="utf-8"))}
    solicitudes = json.loads((DATOS / "solicitudes.json").read_text(encoding="utf-8"))

    assert {s["solicitud"]["trabajador_id"] for s in solicitudes} <= padron


def _leer(nombre: str):
    return json.loads((DATOS / f"{nombre}.json").read_text(encoding="utf-8"))


def test_historial_de_trabajos_cuadra_con_el_padron_los_trabajos_y_los_incidentes():
    padron = {t["trabajador_id"] for t in _leer("trabajadores")}
    trabajos = {t["trabajo_id"] for t in _leer("trabajos")}
    incidentes = {i["id"]: i["trabajador_id"] for i in _leer("incidentes_etiquetados")}
    historial = _leer("historial_trabajos")

    assert [(h["historial_trabajo_id"], h["trabajo_id"], h["costo_real"], h["duracion_real"])
            for h in historial if h["trabajador_id"] == "T-011"] == [
        ("HT-0021", 11, 600.0, 3.0), ("HT-0022", 11, 2950.0, 12.0), ("HT-0023", 11, 1000.0, 4.0),
    ]
    assert {h["trabajador_id"] for h in historial} <= padron
    assert {h["trabajo_id"] for h in historial} <= trabajos
    assert all(incidentes[h["incidente_id"]] == h["trabajador_id"] for h in historial if h["incidente_id"])


def test_catalogo_de_trabajos_viene_de_la_planilla_y_usa_el_vocabulario():
    trabajos = _leer("trabajos")

    assert [t["trabajo_id"] for t in trabajos] == list(range(1, 13))
    assert {t["tipo_tarea"] for t in trabajos} <= set(TIPOS_TAREA)
    assert next(t for t in trabajos if t["trabajo_id"] == 11)["tipo_trabajo_minero"] == "Acarreo subterráneo con scooptram"


def test_padron_trae_fechas_y_raul_coincide_con_la_planilla():
    padron = _leer("trabajadores")
    raul = next(t for t in padron if t["trabajador_id"] == "T-011")

    assert all(t["fecha_ingreso"] and t["fecha_nacimiento"] for t in padron)
    assert (raul["fecha_nacimiento"], raul["fecha_ingreso"]) == ("1981-08-15", "2020-07-27")


def test_avatar_reenviado_sin_datos_clinicos(cliente):
    avatar = cliente.get("/trabajadores/T-001/avatar").json()

    assert avatar["estado_visual"]["energia"] == 35
    assert "diagnostico" not in json.dumps(avatar)


def test_gemelo_no_confiable_bloquea_sin_consultarlo(cliente):
    ptw = _solicitar(cliente, GemeloRevocado())

    assert ptw["consultas"]["gemelo"]["estado"] == "error"
    assert ptw["propuesta"]["nivel"] == "rojo"
    assert "No se pudo confirmar la aptitud del trabajador en la zona clínica." in ptw["propuesta"]["porque"]
    assert {f["id"]: f["motivo"] for f in ptw["nanda"]}["vigia-gemelo"] == "credencial revocada por la autoridad"


def test_claude_no_recibe_datos_de_salud_ni_del_trabajador(cliente, monkeypatch):
    contextos = []
    monkeypatch.setattr(llm, "redactar", lambda sistema, contenido, **_: contextos.append(contenido))
    ptw = _solicitar(cliente)

    assert ptw["propuesta"]["nivel"] == "ambar" and contextos
    for motivo in ptw["consultas"]["gemelo"]["data"]["motivo_visible"].split("; "):
        assert motivo not in contextos[0]
    assert "T-001" not in contextos[0] and "Juan" not in contextos[0]


def test_log_de_bloqueo_no_incluye_datos_de_salud(cliente, caplog):
    _solicitar(cliente, ClientesEscenario(gemelo={"apto_para_tarea": "no_apto", "motivo_visible": "Descanso insuficiente"}))

    assert "bloqueado" in caplog.text
    assert "Descanso insuficiente" not in caplog.text


def test_langfuse_recibe_las_trazas_enmascaradas():
    traza = {
        "solicitud": {"trabajador_id": "T-001", "tarea": "perforación"},
        "trabajador_nombre": "Juan Mamani",
        "consultas": {"gemelo": {"data": {"motivo_visible": "Descanso insuficiente"}}},
        "propuesta": {"nivel": "rojo", "porque": ["Trabajador no apto hoy: Descanso insuficiente."]},
    }
    texto = json.dumps(enmascarar(data=traza), ensure_ascii=False)

    for dato in ("T-001", "Juan", "Descanso"):
        assert dato not in texto
    assert "perforación" in texto and "rojo" in texto


# --- Seguridad NANDA con agentes reales detras de httpx --------------------------------------

NANDA = "http://nanda"
URLS = {"vigia-incidentes": "http://incidentes", "vigia-area": "http://area", "vigia-gemelo": "http://gemelo"}
RESPUESTAS = {
    "/incidentes/similares": "incidentes_similares",
    "/area/condiciones": "area_condiciones",
    "/gemelo/aptitud": "gemelo_aptitud",
}
CONSULTA_APTITUD = ConsultaAptitud(
    trabajador_id="T-001", tipo_tarea="perforacion", turno="noche", altitud_msnm=4210,
    tipo_mineria="subterranea", empleador="contratista",
)


def _ficha(agent_id, clave, autoridades):
    ahora = datetime.now(timezone.utc)
    facts = AgentFacts(
        id=agent_id, agent_name=agent_id, label="Vigía", description="Prueba", version="0.1.0",
        provider=Proveedor(name="Vigía"), endpoints=Endpoints(static=[URLS[agent_id]]),
        skills=[Habilidad(id="consulta", description="Prueba")],
        issued_at=ahora.isoformat(), expires_at=(ahora + timedelta(minutes=10)).isoformat(),
    )
    claims = ZONA_CLINICA if agent_id == "vigia-gemelo" else {}
    return firmar(facts, clave, emitir(nueva_credencial(agent_id, clave_publica_b64(clave), claims, 1), autoridades))


class Red:
    """Indice NANDA y agentes falsos: cada agente firma sus respuestas con su clave."""

    def __init__(self):
        self.claves = {agent_id: Ed25519PrivateKey.generate() for agent_id in URLS}
        self.fichas = {}
        self.revocaciones = None
        self.indice_caido = False
        self.alterar_respuestas = False
        self.llamadas = []
        for agent_id in URLS:
            autoridades = {SSO: clave_dev(SSO), SALUD: clave_dev(SALUD)} if agent_id == "vigia-gemelo" else {SSO: clave_dev(SSO)}
            self.certificar(agent_id, autoridades)

    def certificar(self, agent_id, autoridades):
        self.fichas[agent_id] = _ficha(agent_id, self.claves[agent_id], autoridades)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        base, ruta = f"{request.url.scheme}://{request.url.host}", request.url.path
        self.llamadas.append(f"{base}{ruta}")
        if base == NANDA:
            if self.indice_caido:
                return httpx.Response(503)
            if ruta == "/revocaciones":
                return httpx.Response(200, json=self.revocaciones.model_dump(mode="json")) if self.revocaciones else httpx.Response(404)
            ficha = self.fichas.get(ruta.rsplit("/", 1)[1])
            return httpx.Response(200, json=ficha.model_dump(mode="json")) if ficha else httpx.Response(404)
        agent_id = next(a for a, u in URLS.items() if u == base)
        if ruta == "/.well-known/agent-facts":
            return httpx.Response(200, json=self.fichas[agent_id].model_dump(mode="json"))
        cuerpo = json.dumps(_mock(RESPUESTAS.get(ruta, "gemelo_avatar"))).encode()
        firma = firmar_respuesta(self.claves[agent_id], request.headers["x-vigia-nonce"], b"{}" if self.alterar_respuestas else cuerpo)
        return httpx.Response(200, content=cuerpo, headers={"content-type": "application/json", "x-vigia-firma": firma})


@pytest.fixture
def red(monkeypatch):
    red = Red()
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(red), **kw))
    monkeypatch.setenv("NANDA_URL", NANDA)
    for agent_id, url in URLS.items():
        monkeypatch.setenv(f"{agent_id.removeprefix('vigia-').upper()}_URL", url)
    return red


def test_agentes_certificados_se_usan_y_sus_respuestas_se_verifican(red):
    clientes = ClientesAgentes()
    destinos, nanda = asyncio.run(clientes.resolver())
    _, evidencia = asyncio.run(clientes.area(destinos["area"], ConsultaArea(labor="NV-3820 TJ-12")))

    assert all(f["firma"] == "valida" and f["motivo"] is None for f in nanda)
    assert {f["id"]: f["emisores"] for f in nanda}["vigia-gemelo"] == [SALUD, SSO]
    assert destinos["area"]["url"] == "http://area"
    assert evidencia["clave_publica"] == destinos["area"]["clave"]
    assert evidencia["sha256"] == hashlib.sha256(json.dumps(_mock("area_condiciones")).encode()).hexdigest()


def test_gemelo_suplantado_queda_fuera_y_no_se_le_consulta(red):
    red.certificar("vigia-gemelo", {SSO: Ed25519PrivateKey.generate(), SALUD: Ed25519PrivateKey.generate()})
    clientes = ClientesAgentes()
    destinos, nanda = asyncio.run(clientes.resolver())

    assert destinos["gemelo"] is None
    assert {f["id"]: f["motivo"] for f in nanda}["vigia-gemelo"] == f"falta la firma de {SALUD}, {SSO}"
    with pytest.raises(AgenteNoConfiable):
        asyncio.run(clientes.gemelo(destinos["gemelo"], CONSULTA_APTITUD))
    assert not any(llamada.endswith("/gemelo/aptitud") for llamada in red.llamadas)


def test_agente_revocado_por_la_autoridad_queda_fuera(red):
    red.revocaciones = firmar_revocaciones(["vigia-area"], clave_dev(SSO))
    destinos, nanda = asyncio.run(ClientesAgentes().resolver())

    assert destinos["area"] is None
    assert {f["id"]: f["motivo"] for f in nanda}["vigia-area"] == "credencial revocada por la autoridad"


def test_revocacion_falsa_se_ignora(red):
    red.revocaciones = firmar_revocaciones(["vigia-area"], Ed25519PrivateKey.generate())
    destinos, _ = asyncio.run(ClientesAgentes().resolver())
    assert destinos["area"] is not None


def test_respuesta_alterada_se_rechaza(red):
    clientes = ClientesAgentes()
    destinos, _ = asyncio.run(clientes.resolver())
    red.alterar_respuestas = True

    with pytest.raises(AgenteNoConfiable):
        asyncio.run(clientes.area(destinos["area"], ConsultaArea(labor="NV-3820 TJ-12")))


def test_sin_indice_se_verifica_la_ficha_del_propio_agente(red):
    red.indice_caido = True
    destinos, nanda = asyncio.run(ClientesAgentes().resolver())

    assert all(destinos.values()) and all(f["firma"] == "valida" for f in nanda)
    assert "http://area/.well-known/agent-facts" in red.llamadas


def test_ptw_guarda_la_evidencia_firmada_de_cada_agente(cliente, red):
    ptw = _solicitar(cliente, ClientesAgentes())

    assert all(f["firma"] == "valida" for f in ptw["nanda"])
    for agente in ("incidentes", "area", "gemelo"):
        consulta = ptw["consultas"][agente]
        assert consulta["estado"] == "ok"
        assert set(consulta["evidencia"]) == {"nonce", "sha256", "firma", "clave_publica"}
