import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from contracts.agent_facts import (
    SALUD,
    SSO,
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
    motivo_rechazo,
    nueva_credencial,
    revocados_validos,
    verificar_respuesta,
)
from contracts.exportar_schemas import DIRECTORIO, schemas
from contracts.modelos import (
    AvatarGemelo,
    FirmaSupervisor,
    RespuestaAptitud,
    RespuestaArea,
    RespuestaIncidentes,
    ResultadoTarea,
    SolicitudPTW,
)
from contracts.vocabulario import clasificar_labor, clasificar_tarea

MOCKS = Path(__file__).parent / "mocks"


def test_mocks_cumplen_los_contratos():
    pares = {
        "ptw_solicitud": SolicitudPTW,
        "incidentes_similares": RespuestaIncidentes,
        "area_condiciones": RespuestaArea,
        "gemelo_aptitud": RespuestaAptitud,
        "gemelo_avatar": AvatarGemelo,
        "firma": FirmaSupervisor,
        "resultado": ResultadoTarea,
    }
    for nombre, modelo in pares.items():
        modelo.model_validate(json.loads((MOCKS / f"{nombre}.json").read_text(encoding="utf-8")))


def test_gemelo_no_acepta_diagnostico():
    try:
        RespuestaAptitud(trabajador_id="T-001", apto_para_tarea="apto", motivo_visible="", diagnostico="x")
    except ValueError:
        return
    raise AssertionError("diagnostico debe ser siempre null")


def test_schemas_json_estan_al_dia():
    for nombre, contenido in schemas().items():
        assert (DIRECTORIO / f"{nombre}.json").read_text(encoding="utf-8") == contenido, (
            f"Ejecuta: python -m contracts.exportar_schemas ({nombre} desactualizado)"
        )


EMISORES = {e: clave_publica_b64(clave_dev(e)) for e in (SSO, SALUD)}


def _ficha(agent_id="vigia-area", autoridades=None, claims=None, dias=1, clave=None):
    clave = clave or Ed25519PrivateKey.generate()
    autoridades = autoridades or {SSO: clave_dev(SSO)}
    credencial = emitir(nueva_credencial(agent_id, clave_publica_b64(clave), claims or {}, dias), autoridades)
    ahora = datetime.now(timezone.utc)
    facts = AgentFacts(
        id=agent_id, agent_name="Agente", label="Vigía", description="Prueba", version="0.1.0",
        provider=Proveedor(name="Vigía"), endpoints=Endpoints(static=["http://area:8000"]),
        skills=[Habilidad(id="condiciones", description="Gases")],
        issued_at=ahora.isoformat(), expires_at=(ahora + timedelta(minutes=10)).isoformat(),
    )
    return firmar(facts, clave, credencial)


def test_agente_con_credencial_de_la_autoridad_es_confiable():
    assert motivo_rechazo(_ficha(), "vigia-area", EMISORES, set()) is None


def test_credencial_de_otra_autoridad_es_suplantacion():
    impostor = _ficha(autoridades={SSO: Ed25519PrivateKey.generate()})
    assert motivo_rechazo(impostor, "vigia-area", EMISORES, set()) == "falta la firma de vigia-sso"


def test_gemelo_exige_tambien_la_firma_de_salud_ocupacional():
    solo_sso = _ficha("vigia-gemelo", claims={"zona": "clinica"})
    ambas = _ficha("vigia-gemelo", {SSO: clave_dev(SSO), SALUD: clave_dev(SALUD)}, {"zona": "clinica"})

    assert motivo_rechazo(solo_sso, "vigia-gemelo", EMISORES, set()) == f"falta la firma de {SALUD}"
    assert motivo_rechazo(ambas, "vigia-gemelo", EMISORES, set()) is None


def test_gemelo_sin_zona_clinica_no_es_confiable():
    ficha = _ficha("vigia-gemelo", {SSO: clave_dev(SSO), SALUD: clave_dev(SALUD)})
    assert motivo_rechazo(ficha, "vigia-gemelo", EMISORES, set()) == "la credencial no certifica la zona clínica"


def test_credencial_vencida_se_rechaza():
    assert motivo_rechazo(_ficha(dias=-1), "vigia-area", EMISORES, set()) == "credencial fuera de vigencia"


def test_agente_revocado_se_rechaza():
    assert motivo_rechazo(_ficha(), "vigia-area", EMISORES, {"vigia-area"}) == "credencial revocada por la autoridad"


def test_ficha_alterada_se_rechaza():
    ficha = _ficha()
    ficha.facts.endpoints.static = ["http://atacante:8000"]
    assert motivo_rechazo(ficha, "vigia-area", EMISORES, set()) == "firma de la ficha inválida"


def test_ficha_de_otro_agente_se_rechaza():
    assert motivo_rechazo(_ficha(), "vigia-gemelo", EMISORES, set()) == "la ficha no corresponde al agente"


def test_revocaciones_solo_valen_firmadas_por_la_autoridad():
    validas = firmar_revocaciones(["vigia-area"], clave_dev(SSO))
    falsas = firmar_revocaciones([], Ed25519PrivateKey.generate())

    assert revocados_validos(validas, EMISORES) == {"vigia-area"}
    assert revocados_validos(falsas, EMISORES) is None


def test_respuesta_firmada_se_verifica_y_la_alterada_no():
    clave = Ed25519PrivateKey.generate()
    publica = clave_publica_b64(clave)
    firma = firmar_respuesta(clave, "n1", b'{"apto_para_tarea":"apto"}')

    assert verificar_respuesta(publica, "n1", b'{"apto_para_tarea":"apto"}', firma)
    assert not verificar_respuesta(publica, "n1", b'{"apto_para_tarea":"no_apto"}', firma)
    assert not verificar_respuesta(publica, "otro-nonce", b'{"apto_para_tarea":"apto"}', firma)
    assert not verificar_respuesta(publica, "n1", b'{"apto_para_tarea":"apto"}', "no-es-base64")


def test_vocabulario_del_caso_juan():
    assert clasificar_tarea("perforación de frente") == "perforacion"
    assert clasificar_labor("perforación de frente", "NV-3820 TJ-12") == "frente_avance"
    assert clasificar_labor("desatado de rocas", "NV-3900 GA-05") == "galeria"
