"""AgentFacts firmadas con Ed25519 (NANDA).

Excepcion a la regla de claves en espanol: los campos de AgentFacts siguen la
especificacion de NANDA para que el indice oficial pueda leerlos.
"""

import base64
import json
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel


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


class AgentFactsFirmadas(BaseModel):
    facts: AgentFacts
    firma: str
    clave_publica: str
    algoritmo: Literal["Ed25519"] = "Ed25519"


def canonico(facts: AgentFacts) -> bytes:
    return json.dumps(
        facts.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def clave_desde_semilla(semilla_b64: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(semilla_b64))


def clave_publica_b64(privada: Ed25519PrivateKey) -> str:
    cruda = privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(cruda).decode()


def firmar(facts: AgentFacts, privada: Ed25519PrivateKey) -> AgentFactsFirmadas:
    return AgentFactsFirmadas(
        facts=facts,
        firma=base64.b64encode(privada.sign(canonico(facts))).decode(),
        clave_publica=clave_publica_b64(privada),
    )


def verificar(firmadas: AgentFactsFirmadas) -> bool:
    publica = Ed25519PublicKey.from_public_bytes(base64.b64decode(firmadas.clave_publica))
    try:
        publica.verify(base64.b64decode(firmadas.firma), canonico(firmadas.facts))
    except InvalidSignature:
        return False
    return True
