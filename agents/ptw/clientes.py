"""Clientes de los agentes que consulta el orquestador.

- ClientesAgentes: solo usa un agente si NANDA lo certifica: credencial vigente de las
  autoridades de NANDA_EMISORES, no revocado y ficha firmada por la clave certificada.
  Busca la ficha en el indice y, si ahi no sirve, se la pide al propio agente en
  <AGENTE>_URL. Cada respuesta debe venir firmada con esa clave sobre un nonce nuevo.
- ClientesMock: MOCK_MODE=true, responde con los mocks de contracts/mocks.
"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from contracts.agent_facts import (
    GEMELO,
    SALUD,
    SSO,
    AgentFactsFirmadas,
    RevocacionesFirmadas,
    emisores_confiables,
    emisores_validos,
    motivo_rechazo,
    revocados_validos,
    verificar_respuesta,
)
from contracts.modelos import (
    AvatarGemelo,
    ConsultaAptitud,
    ConsultaArea,
    ConsultaIncidentes,
    RegistroIncidente,
    RespuestaAptitud,
    RespuestaArea,
    RespuestaIncidentes,
)

log = logging.getLogger(__name__)

AGENTES = {"incidentes": "vigia-incidentes", "area": "vigia-area", "gemelo": GEMELO}
MOCKS = Path(__file__).resolve().parents[2] / "contracts" / "mocks"


class AgenteNoConfiable(Exception):
    """El agente no tiene credencial valida o su respuesta no viene firmada por la clave certificada."""


def _exigir(destino: dict | None) -> dict:
    if destino is None:
        raise AgenteNoConfiable("el agente no tiene credencial válida: no se consulta")
    return destino


def token_iam(audiencia: str) -> str:
    """ID token de la cuenta de servicio de Cloud Run para invocar un servicio privado."""
    import google.auth.transport.requests
    import google.oauth2.id_token

    return google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), audiencia)


class ClientesAgentes:
    def __init__(self) -> None:
        self.nanda_url = os.getenv("NANDA_URL")
        self.timeout = float(os.getenv("AGENTES_TIMEOUT_S", "20"))
        self.emisores = emisores_confiables()
        self.revocaciones: RevocacionesFirmadas | None = None

    @property
    def revocados(self) -> set[str]:
        return set(self.revocaciones.lista.revocados) if self.revocaciones else set()

    def _motivo(self, firmadas: AgentFactsFirmadas | None, agent_id: str) -> str | None:
        if firmadas is None:
            return "sin ficha en el índice ni en el agente"
        return motivo_rechazo(firmadas, agent_id, self.emisores, self.revocados)

    async def resolver(self) -> tuple[dict[str, dict | None], list[dict]]:
        """Destino verificado de cada agente ({url, clave}, o None si no es confiable) y la traza NANDA."""
        destinos, nanda = {}, []
        async with httpx.AsyncClient(timeout=5) as cliente:
            await self._actualizar_revocaciones(cliente)
            for nombre, agent_id in AGENTES.items():
                firmadas = await self._ficha_del_indice(cliente, agent_id)
                if self._motivo(firmadas, agent_id):
                    firmadas = await self._ficha_del_agente(cliente, nombre) or firmadas
                motivo = self._motivo(firmadas, agent_id)
                if motivo:
                    log.warning("Agente %s descartado: %s", agent_id, motivo)
                destinos[nombre] = None if motivo else {
                    "url": firmadas.facts.endpoints.static[0].rstrip("/"), "clave": firmadas.clave_publica,
                }
                nanda.append({
                    "id": agent_id,
                    "capabilities": [h.id for h in firmadas.facts.skills] if firmadas else [],
                    "firma": "invalida" if motivo else "valida",
                    "emisores": sorted(emisores_validos(firmadas.credencial, self.emisores)) if firmadas else [],
                    "credencial_vence": firmadas.credencial.credential.valid_until if firmadas else None,
                    "motivo": motivo,
                })
        return destinos, nanda

    async def _actualizar_revocaciones(self, cliente: httpx.AsyncClient) -> None:
        """Acepta la lista firmada por SSO solo si es la misma o mas nueva: el indice no puede reponer una vieja."""
        if not self.nanda_url:
            return
        try:
            respuesta = await cliente.get(f"{self.nanda_url}/revocaciones")
            if respuesta.status_code == 404:
                return
            respuesta.raise_for_status()
            lista = RevocacionesFirmadas.model_validate(respuesta.json())
        except (httpx.HTTPError, ValidationError) as e:
            log.warning("Revocaciones no disponibles (%s): se usa la ultima lista valida", e)
            return
        if revocados_validos(lista, self.emisores) is None:
            log.warning("Lista de revocaciones sin firma de la autoridad: se ignora")
            return
        if self.revocaciones is None or datetime.fromisoformat(lista.lista.emitido_en) >= datetime.fromisoformat(
            self.revocaciones.lista.emitido_en
        ):
            self.revocaciones = lista

    async def _ficha_del_indice(self, cliente: httpx.AsyncClient, agent_id: str) -> AgentFactsFirmadas | None:
        if not self.nanda_url:
            return None
        return await self._descargar_ficha(cliente, f"{self.nanda_url}/resolve/{agent_id}", {})

    async def _ficha_del_agente(self, cliente: httpx.AsyncClient, nombre: str) -> AgentFactsFirmadas | None:
        url = os.getenv(f"{nombre.upper()}_URL", "").rstrip("/")
        if not url:
            return None
        cabeceras = {}
        if nombre == "gemelo" and _gemelo_con_iam():
            cabeceras["Authorization"] = f"Bearer {await asyncio.to_thread(token_iam, url)}"
        return await self._descargar_ficha(cliente, f"{url}/.well-known/agent-facts", cabeceras)

    async def _descargar_ficha(self, cliente: httpx.AsyncClient, url: str, cabeceras: dict) -> AgentFactsFirmadas | None:
        try:
            respuesta = await cliente.get(url, headers=cabeceras)
            respuesta.raise_for_status()
            return AgentFactsFirmadas.model_validate(respuesta.json())
        except (httpx.HTTPError, ValidationError) as e:
            log.warning("Sin ficha NANDA en %s (%s)", url, e)
            return None

    async def _llamar(
        self, destino: dict | None, metodo: str, ruta: str, cuerpo: dict | None = None, con_iam: bool = False
    ) -> tuple[dict, dict]:
        destino = _exigir(destino)
        nonce = secrets.token_urlsafe(16)
        cabeceras = {"x-vigia-nonce": nonce}
        if con_iam:
            cabeceras["Authorization"] = f"Bearer {await asyncio.to_thread(token_iam, destino['url'])}"
        async with httpx.AsyncClient(timeout=self.timeout) as cliente:
            respuesta = await cliente.request(metodo, f"{destino['url']}{ruta}", json=cuerpo, headers=cabeceras)
        respuesta.raise_for_status()
        firma = respuesta.headers.get("x-vigia-firma", "")
        if not verificar_respuesta(destino["clave"], nonce, respuesta.content, firma):
            raise AgenteNoConfiable(f"{destino['url']}{ruta}: la respuesta no viene firmada por el agente certificado")
        evidencia = {
            "nonce": nonce, "sha256": hashlib.sha256(respuesta.content).hexdigest(),
            "firma": firma, "clave_publica": destino["clave"],
        }
        return respuesta.json(), evidencia

    async def incidentes(self, destino: dict | None, consulta: ConsultaIncidentes) -> tuple[RespuestaIncidentes, dict]:
        datos, evidencia = await self._llamar(destino, "POST", "/incidentes/similares", consulta.model_dump())
        return RespuestaIncidentes.model_validate(datos), evidencia

    async def area(self, destino: dict | None, consulta: ConsultaArea) -> tuple[RespuestaArea, dict]:
        datos, evidencia = await self._llamar(destino, "POST", "/area/condiciones", consulta.model_dump())
        return RespuestaArea.model_validate(datos), evidencia

    async def gemelo(self, destino: dict | None, consulta: ConsultaAptitud) -> tuple[RespuestaAptitud, dict]:
        datos, evidencia = await self._llamar(
            destino, "POST", "/gemelo/aptitud", consulta.model_dump(), con_iam=_gemelo_con_iam()
        )
        return RespuestaAptitud.model_validate(datos), evidencia

    async def avatar(self, destino: dict | None, trabajador_id: str) -> AvatarGemelo:
        datos, _ = await self._llamar(destino, "GET", f"/gemelo/{trabajador_id}/avatar", con_iam=_gemelo_con_iam())
        return AvatarGemelo.model_validate(datos)

    async def registrar_incidente(self, destino: dict | None, registro: RegistroIncidente) -> None:
        await self._llamar(destino, "POST", "/incidentes/registrar", registro.model_dump())


def _gemelo_con_iam() -> bool:
    return os.getenv("GEMELO_IAM", "false").lower() == "true"


def _mock(nombre: str) -> dict:
    return json.loads((MOCKS / f"{nombre}.json").read_text(encoding="utf-8"))


class ClientesMock:
    def __init__(self) -> None:
        self.registrados: list[RegistroIncidente] = []

    async def resolver(self) -> tuple[dict[str, dict | None], list[dict]]:
        destinos = {nombre: {"url": f"mock://{agent_id}", "clave": ""} for nombre, agent_id in AGENTES.items()}
        capacidades = {"vigia-incidentes": ["similares", "registrar"], "vigia-area": ["condiciones"],
                       GEMELO: ["aptitud", "avatar"]}
        nanda = [
            {"id": agent_id, "capabilities": capacidades[agent_id], "firma": "valida",
             "emisores": [SALUD, SSO] if agent_id == GEMELO else [SSO], "credencial_vence": None, "motivo": None}
            for agent_id in AGENTES.values()
        ]
        return destinos, nanda

    async def avatar(self, destino: dict | None, trabajador_id: str) -> AvatarGemelo:
        _exigir(destino)
        return AvatarGemelo.model_validate({**_mock("gemelo_avatar"), "trabajador_id": trabajador_id})

    async def incidentes(self, destino: dict | None, consulta: ConsultaIncidentes) -> tuple[RespuestaIncidentes, None]:
        _exigir(destino)
        return RespuestaIncidentes.model_validate(_mock("incidentes_similares")), None

    async def area(self, destino: dict | None, consulta: ConsultaArea) -> tuple[RespuestaArea, None]:
        _exigir(destino)
        return RespuestaArea.model_validate({**_mock("area_condiciones"), "labor": consulta.labor}), None

    async def gemelo(self, destino: dict | None, consulta: ConsultaAptitud) -> tuple[RespuestaAptitud, None]:
        _exigir(destino)
        datos = {**_mock("gemelo_aptitud"), "trabajador_id": consulta.trabajador_id}
        return RespuestaAptitud.model_validate(datos), None

    async def registrar_incidente(self, destino: dict | None, registro: RegistroIncidente) -> None:
        _exigir(destino)
        self.registrados.append(registro)
