"""Publicacion de AgentFacts (GET /.well-known/agent-facts), firma de respuestas y registro en el indice NANDA.

Cada agente presenta la credencial que le emitio la autoridad (AGENT_CREDENCIAL), publica
fichas de vida corta y firma con su clave Ed25519 cada respuesta pedida con x-vigia-nonce.
"""

import asyncio
import base64
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, Request, Response

from contracts.agent_facts import (
    DIAS_CREDENCIAL,
    DIAS_ZONA_CLINICA,
    SALUD,
    SSO,
    AgentFacts,
    AgentFactsFirmadas,
    CredencialFirmada,
    Endpoints,
    Habilidad,
    Proveedor,
    clave_de,
    clave_dev,
    clave_publica_b64,
    emitir,
    firmar,
    firmar_respuesta,
    nueva_credencial,
)

log = logging.getLogger(__name__)

VERSION = "0.1.0"
TTL_FACTS = timedelta(minutes=10)


def _credencial(agent_id: str, clave_publica: str, claims: dict) -> CredencialFirmada:
    texto = os.getenv("AGENT_CREDENCIAL")
    if texto:
        return CredencialFirmada.model_validate_json(base64.b64decode(texto))
    log.warning("AGENT_CREDENCIAL no definida: credencial de desarrollo (solo para local)")
    autoridades = {SSO: clave_dev(SSO)} | ({SALUD: clave_dev(SALUD)} if claims else {})
    dias = DIAS_ZONA_CLINICA if claims else DIAS_CREDENCIAL
    return emitir(nueva_credencial(agent_id, clave_publica, claims, dias), autoridades)


class PublicadorFacts:
    def __init__(
        self, agent_id: str, nombre: str, descripcion: str, habilidades: dict[str, str], claims: dict | None = None
    ):
        self.agent_id = agent_id
        self.nombre = nombre
        self.descripcion = descripcion
        self.habilidades = habilidades
        self.clave = clave_de("AGENT_ED25519_KEY", agent_id)
        self.credencial = _credencial(agent_id, clave_publica_b64(self.clave), claims or {})

    def facts_firmadas(self) -> AgentFactsFirmadas:
        ahora = datetime.now(timezone.utc)
        facts = AgentFacts(
            id=self.agent_id,
            agent_name=self.nombre,
            label="Vigía",
            description=self.descripcion,
            version=VERSION,
            provider=Proveedor(name="Vigía - PETAR dinamico"),
            endpoints=Endpoints(static=[os.getenv("AGENT_URL", "http://localhost:8000")]),
            skills=[Habilidad(id=k, description=v) for k, v in self.habilidades.items()],
            capabilities={"authentication": {"methods": [os.getenv("AGENT_AUTH", "none")]}},
            issued_at=ahora.isoformat(),
            expires_at=(ahora + TTL_FACTS).isoformat(),
        )
        return firmar(facts, self.clave, self.credencial)

    def montar(self, app: FastAPI) -> None:
        @app.get("/.well-known/agent-facts", response_model=AgentFactsFirmadas, tags=["nanda"])
        def agent_facts() -> AgentFactsFirmadas:
            return self.facts_firmadas()

        @app.middleware("http")
        async def firmar_respuestas(request: Request, call_next) -> Response:
            respuesta = await call_next(request)
            nonce = request.headers.get("x-vigia-nonce")
            if not nonce:
                return respuesta
            cuerpo = b"".join([trozo async for trozo in respuesta.body_iterator])
            cabeceras = {**respuesta.headers, "x-vigia-firma": firmar_respuesta(self.clave, nonce, cuerpo)}
            return Response(cuerpo, status_code=respuesta.status_code, headers=cabeceras)

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
