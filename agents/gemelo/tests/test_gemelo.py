import base64
import json
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from fastapi.testclient import TestClient

from agents.gemelo.app import app
from agents.gemelo.repo import Cofre, semilla
from contracts.agent_facts import AgentFactsFirmadas, emisores_confiables, motivo_rechazo, verificar_respuesta

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


CONSULTA_RAUL = {**CONSULTA_JUAN, "trabajador_id": "T-011", "turno": "dia", "altitud_msnm": 3800,
                 "empleador": "titular"}


def test_restriccion_medica_impide_su_tarea_sin_revelar_la_condicion():
    cuerpo = _aptitud({**CONSULTA_RAUL, "tipo_tarea": "carguio"})
    texto = json.dumps(cuerpo, ensure_ascii=False).lower()

    assert cuerpo["apto_para_tarea"] == "no_apto"
    assert cuerpo["motivo_visible"] == "Restricción médica vigente para esta tarea: consultar a salud ocupacional"
    for dato_privado in ("asma", "lumbalgia", "tobillo", "neumoconiosis", "polvo", "vibración"):
        assert dato_privado not in texto


def test_historial_de_salud_completo_queda_solo_en_el_gemelo():
    raul = next(g for g in semilla() if g["trabajador_id"] == "T-011")["datos_clinicos"]
    cuerpo = json.dumps(_aptitud({**CONSULTA_RAUL, "tipo_tarea": "carguio"}), ensure_ascii=False).lower()

    assert raul["alergias"] == "Ácaros del polvo doméstico"
    assert raul["controles_vencidos"] == 0
    assert [e["salud_id"] for e in raul["evaluaciones"]] == [18, 19, 20, 21, 22, 23]
    assert raul["descansos_medicos"] == [{"incidente_id": "INC-0022", "dias": 45}, {"incidente_id": "INC-0023", "dias": 3}]
    assert all({"alergias", "medicacion_habitual", "controles_vencidos"} <= set(g["datos_clinicos"]) for g in semilla())
    for dato_privado in ("ácaros", "salbutamol", "corticoide"):
        assert dato_privado not in cuerpo


def test_restriccion_medica_no_alcanza_tareas_no_restringidas():
    assert _aptitud({**CONSULTA_RAUL, "tipo_tarea": "mantenimiento"})["apto_para_tarea"] == "apto_con_observaciones"


def test_trabajador_descansado_es_apto():
    cuerpo = _aptitud({**CONSULTA_JUAN, "trabajador_id": "T-002", "altitud_msnm": 3400,
                       "tipo_mineria": "tajo_abierto", "turno": "dia", "tipo_tarea": "carguio"})
    assert cuerpo["apto_para_tarea"] == "apto"


def test_trabajador_sin_gemelo_no_es_apto():
    assert _aptitud({**CONSULTA_JUAN, "trabajador_id": "T-999"})["apto_para_tarea"] == "no_apto"


def test_no_hay_endpoints_de_detalle():
    assert {r.path for r in app.routes} == {
        "/gemelo/aptitud", "/gemelo/{trabajador_id}/avatar", "/health", "/.well-known/agent-facts",
    }


def _avatar(trabajador_id: str) -> dict:
    with TestClient(app) as cliente:
        respuesta = cliente.get(f"/gemelo/{trabajador_id}/avatar")
    assert respuesta.status_code == 200
    return respuesta.json()


def test_avatar_de_juan():
    avatar = _avatar("T-001")
    visual = avatar["estado_visual"]

    assert (avatar["nombre"], avatar["empleador"]) == ("Juan Mamani", "contratista")
    assert visual["energia"] == 35
    assert (visual["dia_rotacion"], visual["total_rotacion"]) == (12, 14)
    assert visual["exposicion_nivel"] == "alta"
    assert visual["apto_para_tarea"] == "apto_con_observaciones"
    historial = visual["historial_energia"]
    assert len(historial) == 14 and historial == sorted(historial, reverse=True) and historial[-1] == 35


def test_avatar_de_juan_descansado():
    visual = _avatar("T-001-D3")["estado_visual"]
    assert (visual["energia"], visual["dia_rotacion"], visual["apto_para_tarea"]) == (85, 3, "apto")


def test_avatar_no_contiene_campos_clinicos():
    avatar = _avatar("T-001")
    claves = set(avatar) | set(avatar["estado_visual"])
    texto = json.dumps(avatar, ensure_ascii=False).lower()

    assert set(avatar) == {"trabajador_id", "nombre", "cargo", "empresa", "empleador", "seed",
                           "color_casco", "estado_visual"}
    for prohibido in ("diagnostico", "datos_clinicos", "restricciones", "emo_vigente_hasta", "sueno_h", "foto"):
        assert prohibido not in claves
    for dato_privado in ("hipoacusia", "emo_vigente", "5.1"):
        assert dato_privado not in texto


def test_gemelo_certificado_como_zona_clinica_firma_sus_respuestas():
    with TestClient(app) as cliente:
        ficha = AgentFactsFirmadas.model_validate(cliente.get("/.well-known/agent-facts").json())
        respuesta = cliente.post("/gemelo/aptitud", json=CONSULTA_JUAN, headers={"x-vigia-nonce": "n-1"})

    assert motivo_rechazo(ficha, "vigia-gemelo", emisores_confiables(), set()) is None
    assert verificar_respuesta(ficha.clave_publica, "n-1", respuesta.content, respuesta.headers["x-vigia-firma"])
    assert not verificar_respuesta(ficha.clave_publica, "otro", respuesta.content, respuesta.headers["x-vigia-firma"])


COFRE = Cofre(base64.b64encode(bytes(32)).decode())
JUAN = semilla()[0]


def test_fila_clinica_se_guarda_seudonimizada_y_cifrada():
    seudonimo = COFRE.seudonimo("T-001")
    datos = COFRE.cifrar(seudonimo, JUAN)

    assert "T-001" not in seudonimo and len(seudonimo) == 64
    for dato in (b"T-001", b"Juan", b"Hipoacusia", b"sueno_h"):
        assert dato not in datos
    assert COFRE.descifrar(seudonimo, datos) == JUAN


def test_fila_cifrada_no_se_puede_mover_a_otro_seudonimo():
    datos = COFRE.cifrar(COFRE.seudonimo("T-001"), JUAN)
    with pytest.raises(InvalidTag):
        COFRE.descifrar(COFRE.seudonimo("T-002"), datos)


def test_sin_la_clave_no_se_vincula_ni_se_lee():
    otro = Cofre(base64.b64encode(bytes([1] * 32)).decode())
    seudonimo = COFRE.seudonimo("T-001")

    assert otro.seudonimo("T-001") != seudonimo
    with pytest.raises(InvalidTag):
        otro.descifrar(seudonimo, COFRE.cifrar(seudonimo, JUAN))


def test_avatar_de_trabajador_inexistente_es_404():
    with TestClient(app) as cliente:
        assert cliente.get("/gemelo/T-999/avatar").status_code == 404
