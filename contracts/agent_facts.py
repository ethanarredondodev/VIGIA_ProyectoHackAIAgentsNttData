"""AgentFacts firmadas con Ed25519 y credenciales de la zona de confianza de Vigía (NANDA).

Excepcion a la regla de claves en espanol: los campos de AgentFacts siguen la
especificacion de NANDA para que el indice oficial pueda leerlos.

Modelo de confianza (NANDA, "Beyond DNS", secciones V y VII): una ficha no se
autocertifica. La autoridad emisora (SSO de la minera) firma una credencial que une el
id del agente con su clave publica y su vigencia; el gemelo necesita ademas la firma de
Salud Ocupacional. Los clientes solo aceptan emisores de su lista blanca, descartan
agentes revocados y exigen que cada respuesta venga firmada por la clave certificada.

Autoridad (las semillas nunca llegan a los servicios; sin ellas se usan claves de desarrollo):
  python -m contracts.agent_facts emisores                          SEMILLA_SSO, SEMILLA_SALUD
  python -m contracts.agent_facts emitir vigia-gemelo --zona-clinica  + SEMILLA_AGENTE
  python -m contracts.agent_facts revocar vigia-area --nanda URL      SEMILLA_SSO (sin ids: restaura)
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel

log = logging.getLogger(__name__)

SSO = "vigia-sso"
SALUD = "vigia-salud-ocupacional"
GEMELO = "vigia-gemelo"
ZONA_CLINICA = {"zona": "clinica"}

# Vigencia segun criticidad (NANDA: TTL mas corto para agentes de salud).
DIAS_CREDENCIAL = 30
DIAS_ZONA_CLINICA = 7


class Proveedor(BaseModel):
    name: str
    url: str = ""


class Endpoints(BaseModel):
    static: list[str]


class Habilidad(BaseModel):
    id: str
    description: str
    input_modes: list[str] = ["application/json"]
    output_modes: list[str] = ["application/json"]


class AgentFacts(BaseModel):
    id: str
    agent_name: str
    label: str
    description: str
    version: str
    provider: Proveedor
    endpoints: Endpoints
    skills: list[Habilidad]
    capabilities: dict = {}
    issued_at: str
    expires_at: str


class Credencial(BaseModel):
    """Credencial verificable simplificada (W3C VC 2.0 sin JSON-LD): la emite la autoridad, no el agente."""

    subject: str
    public_key: str
    claims: dict = {}
    valid_from: str
    valid_until: str


class Prueba(BaseModel):
    issuer: str
    proof_value: str


class CredencialFirmada(BaseModel):
    credential: Credencial
    proofs: list[Prueba]


class AgentFactsFirmadas(BaseModel):
    facts: AgentFacts
    firma: str
    clave_publica: str
    credencial: CredencialFirmada
    algoritmo: Literal["Ed25519"] = "Ed25519"


class Revocaciones(BaseModel):
    revocados: list[str]
    emitido_en: str


class RevocacionesFirmadas(BaseModel):
    """Lista de agentes revocados, firmada por la autoridad SSO."""

    lista: Revocaciones
    proof_value: str


def canonico(modelo: BaseModel) -> bytes:
    return json.dumps(
        modelo.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def clave_desde_semilla(semilla_b64: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(semilla_b64))


def clave_dev(etiqueta: str) -> Ed25519PrivateKey:
    """Clave derivada de un texto publico: solo para desarrollo local."""
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(f"vigia-dev:{etiqueta}".encode()).digest())


def clave_de(variable: str, etiqueta: str) -> Ed25519PrivateKey:
    semilla = os.getenv(variable)
    if semilla:
        return clave_desde_semilla(semilla)
    log.warning("%s no definida: clave de desarrollo de %s (solo para local)", variable, etiqueta)
    return clave_dev(etiqueta)


def clave_publica_b64(privada: Ed25519PrivateKey) -> str:
    cruda = privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(cruda).decode()


def _firmar_b64(privada: Ed25519PrivateKey, datos: bytes) -> str:
    return base64.b64encode(privada.sign(datos)).decode()


def _firma_valida(publica_b64: str, firma_b64: str, datos: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(publica_b64)).verify(base64.b64decode(firma_b64), datos)
    except (InvalidSignature, ValueError):
        return False
    return True


def emisores_confiables() -> dict[str, str]:
    """Lista blanca de autoridades (id -> clave publica): NANDA_EMISORES="vigia-sso:<clave>;vigia-salud-ocupacional:<clave>"."""
    texto = os.getenv("NANDA_EMISORES")
    if texto:
        return dict(par.split(":", 1) for par in texto.split(";") if par)
    log.warning("NANDA_EMISORES no definida: se confia en las autoridades de desarrollo (solo para local)")
    return {e: clave_publica_b64(clave_dev(e)) for e in (SSO, SALUD)}


def nueva_credencial(agent_id: str, clave_publica: str, claims: dict, dias: float) -> Credencial:
    ahora = datetime.now(timezone.utc)
    return Credencial(
        subject=agent_id, public_key=clave_publica, claims=claims,
        valid_from=ahora.isoformat(), valid_until=(ahora + timedelta(days=dias)).isoformat(),
    )


def emitir(credencial: Credencial, autoridades: dict[str, Ed25519PrivateKey]) -> CredencialFirmada:
    datos = canonico(credencial)
    return CredencialFirmada(
        credential=credencial,
        proofs=[Prueba(issuer=emisor, proof_value=_firmar_b64(clave, datos)) for emisor, clave in autoridades.items()],
    )


def firmar(facts: AgentFacts, privada: Ed25519PrivateKey, credencial: CredencialFirmada) -> AgentFactsFirmadas:
    return AgentFactsFirmadas(
        facts=facts,
        firma=_firmar_b64(privada, canonico(facts)),
        clave_publica=clave_publica_b64(privada),
        credencial=credencial,
    )


def emisores_validos(credencial: CredencialFirmada, emisores: dict[str, str]) -> set[str]:
    datos = canonico(credencial.credential)
    return {
        p.issuer for p in credencial.proofs
        if p.issuer in emisores and _firma_valida(emisores[p.issuer], p.proof_value, datos)
    }


def motivo_rechazo(
    firmadas: AgentFactsFirmadas, agent_id: str, emisores: dict[str, str], revocados: set[str]
) -> str | None:
    """None si el agente es confiable para la lista blanca `emisores`; si no, el motivo."""
    ahora = datetime.now(timezone.utc)
    credencial = firmadas.credencial.credential
    if firmadas.facts.id != agent_id or credencial.subject != agent_id:
        return "la ficha no corresponde al agente"
    if agent_id in revocados:
        return "credencial revocada por la autoridad"
    faltan = ({SSO, SALUD} if agent_id == GEMELO else {SSO}) - emisores_validos(firmadas.credencial, emisores)
    if faltan:
        return f"falta la firma de {', '.join(sorted(faltan))}"
    if not datetime.fromisoformat(credencial.valid_from) <= ahora < datetime.fromisoformat(credencial.valid_until):
        return "credencial fuera de vigencia"
    if agent_id == GEMELO and credencial.claims.get("zona") != "clinica":
        return "la credencial no certifica la zona clínica"
    if credencial.public_key != firmadas.clave_publica or not _firma_valida(
        firmadas.clave_publica, firmadas.firma, canonico(firmadas.facts)
    ):
        return "firma de la ficha inválida"
    if ahora >= datetime.fromisoformat(firmadas.facts.expires_at):
        return "ficha vencida"
    return None


def firmar_revocaciones(revocados: list[str], privada_sso: Ed25519PrivateKey) -> RevocacionesFirmadas:
    lista = Revocaciones(revocados=sorted(set(revocados)), emitido_en=datetime.now(timezone.utc).isoformat())
    return RevocacionesFirmadas(lista=lista, proof_value=_firmar_b64(privada_sso, canonico(lista)))


def revocados_validos(firmadas: RevocacionesFirmadas, emisores: dict[str, str]) -> set[str] | None:
    """Los ids revocados si la lista la firmo la autoridad SSO; None si no."""
    if not _firma_valida(emisores.get(SSO, ""), firmadas.proof_value, canonico(firmadas.lista)):
        return None
    return set(firmadas.lista.revocados)


def _mensaje_respuesta(nonce: str, cuerpo: bytes) -> bytes:
    return f"{nonce}\n{hashlib.sha256(cuerpo).hexdigest()}".encode()


def firmar_respuesta(privada: Ed25519PrivateKey, nonce: str, cuerpo: bytes) -> str:
    return _firmar_b64(privada, _mensaje_respuesta(nonce, cuerpo))


def verificar_respuesta(clave_publica: str, nonce: str, cuerpo: bytes, firma: str) -> bool:
    return _firma_valida(clave_publica, firma, _mensaje_respuesta(nonce, cuerpo))


def _cli() -> None:
    parser = argparse.ArgumentParser(prog="python -m contracts.agent_facts", description="Autoridad NANDA de Vigía.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("emisores", help="Imprime NANDA_EMISORES con las claves publicas de las autoridades")
    emision = comandos.add_parser("emitir", help="Imprime AGENT_CREDENCIAL (base64) para un agente")
    emision.add_argument("agente")
    emision.add_argument("--zona-clinica", action="store_true", help="Co-firma Salud Ocupacional")
    revocacion = comandos.add_parser("revocar", help="Publica la lista firmada de revocados (sin ids: restaura)")
    revocacion.add_argument("agentes", nargs="*")
    revocacion.add_argument("--nanda", default=os.getenv("NANDA_URL", "http://localhost:8010"))
    args = parser.parse_args()

    sso = clave_de("SEMILLA_SSO", SSO)
    if args.comando == "emisores":
        print(f"{SSO}:{clave_publica_b64(sso)};{SALUD}:{clave_publica_b64(clave_de('SEMILLA_SALUD', SALUD))}")
    elif args.comando == "emitir":
        autoridades = {SSO: sso} | ({SALUD: clave_de("SEMILLA_SALUD", SALUD)} if args.zona_clinica else {})
        publica = clave_publica_b64(clave_de("SEMILLA_AGENTE", args.agente))
        credencial = nueva_credencial(
            args.agente, publica, ZONA_CLINICA if args.zona_clinica else {},
            DIAS_ZONA_CLINICA if args.zona_clinica else DIAS_CREDENCIAL,
        )
        print(base64.b64encode(emitir(credencial, autoridades).model_dump_json().encode()).decode())
    else:
        peticion = urllib.request.Request(
            f"{args.nanda.rstrip('/')}/revocaciones", method="POST",
            data=firmar_revocaciones(args.agentes, sso).model_dump_json().encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            print(respuesta.read().decode())


if __name__ == "__main__":
    _cli()
