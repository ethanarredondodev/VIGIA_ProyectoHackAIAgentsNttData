"""Interfaz del indice de agentes y sus implementaciones.

- IndiceLocal: en memoria. La app solo le entrega fichas con credencial valida.
- IndiceNandaOficial: envuelve al local y ademas publica/consulta el registry oficial
  de NANDA (repositorio projnanda/adapter). Se activa con NANDA_OFICIAL_URL.
"""

import logging
from typing import Protocol

import httpx
from pydantic import ValidationError

from contracts.agent_facts import AgentFactsFirmadas, motivo_rechazo

log = logging.getLogger(__name__)


class IndiceAgentes(Protocol):
    def registrar(self, firmadas: AgentFactsFirmadas) -> None: ...

    def resolver(self, agent_id: str) -> AgentFactsFirmadas | None: ...

    def listar(self) -> list[AgentFactsFirmadas]: ...


class IndiceLocal:
    def __init__(self) -> None:
        self._facts: dict[str, AgentFactsFirmadas] = {}

    def registrar(self, firmadas: AgentFactsFirmadas) -> None:
        self._facts[firmadas.facts.id] = firmadas

    def resolver(self, agent_id: str) -> AgentFactsFirmadas | None:
        return self._facts.get(agent_id)

    def listar(self) -> list[AgentFactsFirmadas]:
        return list(self._facts.values())


class IndiceNandaOficial:
    """El registry oficial guarda id -> URL del agente; las AgentFacts firmadas se
    descargan del propio agente (/.well-known/agent-facts) y se verifican aqui."""

    def __init__(self, url_registry: str, local: IndiceLocal, emisores: dict[str, str]) -> None:
        self.url_registry = url_registry.rstrip("/")
        self.local = local
        self.emisores = emisores

    def registrar(self, firmadas: AgentFactsFirmadas) -> None:
        self.local.registrar(firmadas)
        url_agente = firmadas.facts.endpoints.static[0]
        try:
            httpx.post(
                f"{self.url_registry}/register",
                json={"agent_id": firmadas.facts.id, "agent_url": url_agente, "api_url": url_agente},
                timeout=10,
            ).raise_for_status()
        except httpx.HTTPError as e:
            log.warning("No se pudo publicar %s en el registry oficial: %s", firmadas.facts.id, e)

    def resolver(self, agent_id: str) -> AgentFactsFirmadas | None:
        encontrado = self.local.resolver(agent_id)
        if encontrado:
            return encontrado
        try:
            respuesta = httpx.get(f"{self.url_registry}/lookup/{agent_id}", timeout=10)
            respuesta.raise_for_status()
            url_agente = respuesta.json()["agent_url"].rstrip("/")
            facts = httpx.get(f"{url_agente}/.well-known/agent-facts", timeout=10)
            facts.raise_for_status()
            firmadas = AgentFactsFirmadas.model_validate(facts.json())
        except (httpx.HTTPError, KeyError, ValidationError) as e:
            log.warning("No se pudo resolver %s en el registry oficial: %s", agent_id, e)
            return None
        motivo = motivo_rechazo(firmadas, agent_id, self.emisores, set())
        if motivo:
            log.warning("AgentFacts de %s rechazadas desde el registry oficial: %s", agent_id, motivo)
            return None
        self.local.registrar(firmadas)
        return firmadas

    def listar(self) -> list[AgentFactsFirmadas]:
        return self.local.listar()
