"""Clientes de los agentes que consulta el orquestador.

- ClientesAgentes: resuelve cada agente en el indice NANDA (verificando la firma
  Ed25519) y lo llama por HTTP. Si el indice no responde usa <AGENTE>_URL.
- ClientesMock: MOCK_MODE=true, responde con los mocks de contracts/mocks.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx
from pydantic import ValidationError

from contracts.agent_facts import AgentFactsFirmadas, verificar
from contracts.modelos import (
    ConsultaAptitud,
    ConsultaArea,
    ConsultaIncidentes,
    RegistroIncidente,
    RespuestaAptitud,
    RespuestaArea,
    RespuestaIncidentes,
)

log = logging.getLogger(__name__)

AGENTES = {"incidentes": "vigia-incidentes", "area": "vigia-area", "gemelo": "vigia-gemelo"}
MOCKS = Path(__file__).resolve().parents[2] / "contracts" / "mocks"


def token_iam(audiencia: str) -> str:
    """ID token de la cuenta de servicio de Cloud Run para invocar un servicio privado."""
    import google.auth.transport.requests
    import google.oauth2.id_token

    return google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), audiencia)


class ClientesAgentes:
    def __init__(self) -> None:
        self.nanda_url = os.getenv("NANDA_URL")
        self.timeout = float(os.getenv("AGENTES_TIMEOUT_S", "20"))

    async def resolver(self) -> dict[str, str]:
        async with httpx.AsyncClient(timeout=5) as cliente:
            return {
                nombre: await self._resolver_en_nanda(cliente, agent_id) or os.environ[f"{nombre.upper()}_URL"]
                for nombre, agent_id in AGENTES.items()
            }

    async def _resolver_en_nanda(self, cliente: httpx.AsyncClient, agent_id: str) -> str | None:
        if not self.nanda_url:
            return None
        try:
            respuesta = await cliente.get(f"{self.nanda_url}/resolve/{agent_id}")
            respuesta.raise_for_status()
            firmadas = AgentFactsFirmadas.model_validate(respuesta.json())
        except (httpx.HTTPError, ValidationError) as e:
            log.warning("NANDA no resolvio %s (%s): se usa la URL de respaldo", agent_id, e)
            return None
        if firmadas.facts.id != agent_id or not verificar(firmadas):
            log.warning("AgentFacts de %s con firma invalida: se ignoran", agent_id)
            return None
        return firmadas.facts.endpoints.static[0].rstrip("/")

    async def _post(self, url: str, ruta: str, cuerpo: dict, con_iam: bool = False) -> dict:
        cabeceras = {}
        if con_iam:
            cabeceras["Authorization"] = f"Bearer {await asyncio.to_thread(token_iam, url)}"
        async with httpx.AsyncClient(timeout=self.timeout) as cliente:
            respuesta = await cliente.post(f"{url}{ruta}", json=cuerpo, headers=cabeceras)
            respuesta.raise_for_status()
            return respuesta.json()

    async def incidentes(self, url: str, consulta: ConsultaIncidentes) -> RespuestaIncidentes:
        return RespuestaIncidentes.model_validate(await self._post(url, "/incidentes/similares", consulta.model_dump()))

    async def area(self, url: str, consulta: ConsultaArea) -> RespuestaArea:
        return RespuestaArea.model_validate(await self._post(url, "/area/condiciones", consulta.model_dump()))

    async def gemelo(self, url: str, consulta: ConsultaAptitud) -> RespuestaAptitud:
        con_iam = os.getenv("GEMELO_IAM", "false").lower() == "true"
        return RespuestaAptitud.model_validate(
            await self._post(url, "/gemelo/aptitud", consulta.model_dump(), con_iam=con_iam)
        )

    async def registrar_incidente(self, url: str, registro: RegistroIncidente) -> None:
        await self._post(url, "/incidentes/registrar", registro.model_dump())


def _mock(nombre: str) -> dict:
    return json.loads((MOCKS / f"{nombre}.json").read_text(encoding="utf-8"))


class ClientesMock:
    def __init__(self) -> None:
        self.registrados: list[RegistroIncidente] = []

    async def resolver(self) -> dict[str, str]:
        return {nombre: f"mock://{agent_id}" for nombre, agent_id in AGENTES.items()}

    async def incidentes(self, url: str, consulta: ConsultaIncidentes) -> RespuestaIncidentes:
        return RespuestaIncidentes.model_validate(_mock("incidentes_similares"))

    async def area(self, url: str, consulta: ConsultaArea) -> RespuestaArea:
        return RespuestaArea.model_validate({**_mock("area_condiciones"), "labor": consulta.labor})

    async def gemelo(self, url: str, consulta: ConsultaAptitud) -> RespuestaAptitud:
        return RespuestaAptitud.model_validate({**_mock("gemelo_aptitud"), "trabajador_id": consulta.trabajador_id})

    async def registrar_incidente(self, url: str, registro: RegistroIncidente) -> None:
        self.registrados.append(registro)
