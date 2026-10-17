"""Indice NANDA de Vigía: guarda y resuelve AgentFacts con credencial de una autoridad de la lista blanca.

La confianza no depende del orden de registro ni de la memoria del indice: un suplantador
no puede registrarse ni antes ni despues de un reinicio, porque no tiene la firma de la
autoridad. La autoridad SSO puede revocar agentes con una lista firmada.
"""

import os
from datetime import datetime

from fastapi import FastAPI, HTTPException

from contracts.agent_facts import (
    AgentFactsFirmadas,
    RevocacionesFirmadas,
    emisores_confiables,
    motivo_rechazo,
    revocados_validos,
)
from nanda_index.adaptador import IndiceAgentes, IndiceLocal, IndiceNandaOficial

emisores = emisores_confiables()


def crear_indice() -> IndiceAgentes:
    local = IndiceLocal()
    url_oficial = os.getenv("NANDA_OFICIAL_URL")
    return IndiceNandaOficial(url_oficial, local, emisores) if url_oficial else local


app = FastAPI(title="Vigía - Indice NANDA", version="0.1.0")
indice = crear_indice()
revocaciones: RevocacionesFirmadas | None = None


def revocados() -> set[str]:
    return set(revocaciones.lista.revocados) if revocaciones else set()


@app.get("/health")
def salud() -> dict:
    return {"estado": "ok"}


@app.post("/register", status_code=201)
def registrar(firmadas: AgentFactsFirmadas) -> dict:
    motivo = motivo_rechazo(firmadas, firmadas.facts.id, emisores, revocados())
    if motivo:
        raise HTTPException(403, motivo)
    indice.registrar(firmadas)
    return {"id": firmadas.facts.id, "registrado": True}


@app.get("/resolve/{agent_id}", response_model=AgentFactsFirmadas)
def resolver(agent_id: str) -> AgentFactsFirmadas:
    firmadas = indice.resolver(agent_id)
    if firmadas is None or motivo_rechazo(firmadas, agent_id, emisores, revocados()):
        raise HTTPException(404, f"Agente {agent_id} no registrado, vencido o revocado")
    return firmadas


@app.get("/agents", response_model=list[AgentFactsFirmadas])
def listar() -> list[AgentFactsFirmadas]:
    return indice.listar()


@app.post("/revocaciones", status_code=201)
def publicar_revocaciones(lista: RevocacionesFirmadas) -> dict:
    global revocaciones
    if revocados_validos(lista, emisores) is None:
        raise HTTPException(403, "La lista no está firmada por la autoridad SSO")
    if revocaciones and datetime.fromisoformat(lista.lista.emitido_en) <= datetime.fromisoformat(
        revocaciones.lista.emitido_en
    ):
        raise HTTPException(409, "La lista es anterior a la vigente")
    revocaciones = lista
    return {"revocados": lista.lista.revocados}


@app.get("/revocaciones", response_model=RevocacionesFirmadas)
def obtener_revocaciones() -> RevocacionesFirmadas:
    if revocaciones is None:
        raise HTTPException(404, "Sin revocaciones publicadas")
    return revocaciones
