"""Publicacion de AgentFacts firmadas (GET /.well-known/agent-facts) y registro en el indice NANDA."""

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI

from contracts.agent_facts import (
    AgentFacts,
    AgentFactsFirmadas,
    Endpoints,
    Habilidad,
    Proveedor,
    clave_desde_semilla,
    firmar,
)

log = logging.getLogger(__name__)

VERSION = "0.1.0"


def _clave_privada(agent_id: str) -> Ed25519PrivateKey:
    semilla = os.getenv("AGENT_ED25519_KEY")
    if semilla:
        return clave_desde_semilla(semilla)
    log.warning("AGENT_ED25519_KEY no definida: clave de desarrollo derivada del id (solo para local)")
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(f"vigia-dev:{agent_id}".encode()).digest())


class PublicadorFacts:
    def __init__(self, agent_id: str, nombre: str, descripcion: str, habilidades: dict[str, str]):
        self.agent_id = agent_id
        self.nombre = nombre
        self.descripcion = descripcion
        self.habilidades = habilidades
        self.emitido_en = datetime.now(timezone.utc).isoformat()
        self.clave = _clave_privada(agent_id)

    def facts_firmadas(self) -> AgentFactsFirmadas:
        facts = AgentFacts(
            id=self.agent_id,
            agent_name=self.nombre,
            label="Vigia",
            description=self.descripcion,
            version=VERSION,
            provider=Proveedor(name="Vigia - PETAR dinamico"),
            endpoints=Endpoints(static=[os.getenv("AGENT_URL", "http://localhost:8000")]),
            skills=[Habilidad(id=k, description=v) for k, v in self.habilidades.items()],
            capabilities={"authentication": {"methods": [os.getenv("AGENT_AUTH", "none")]}},
            issued_at=self.emitido_en,
        )
        return firmar(facts, self.clave)

    def montar(self, app: FastAPI) -> None:
        @app.get("/.well-known/agent-facts", response_model=AgentFactsFirmadas, tags=["nanda"])
        def agent_facts() -> AgentFactsFirmadas:
            return self.facts_firmadas()

    async def registrar_en_indice(self) -> None:
        """Se registra al arrancar y renueva cada 5 minutos; reintenta cada 5 s si el indice no responde."""
        nanda_url = os.getenv("NANDA_URL")
        if not nanda_url:
            return
        async with httpx.AsyncClient(timeout=10) as cliente:
            while True:
                try:
                    respuesta = await cliente.post(
                        f"{nanda_url}/register", json=self.facts_firmadas().model_dump(mode="json")
                    )
                    respuesta.raise_for_status()
                    log.info("Registrado en NANDA como %s", self.agent_id)
                    espera = 300
                except httpx.HTTPError as e:
                    log.warning("Registro en NANDA fallido (%s), reintento en 5 s", e)
                    espera = 5
                await asyncio.sleep(espera)
