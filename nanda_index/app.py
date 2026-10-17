"""Indice NANDA de Vigia: guarda y resuelve AgentFacts firmadas con Ed25519."""

import os

from fastapi import FastAPI, HTTPException

from contracts.agent_facts import AgentFactsFirmadas, verificar
from nanda_index.adaptador import ClaveNoCoincide, IndiceAgentes, IndiceLocal, IndiceNandaOficial


def crear_indice() -> IndiceAgentes:
    local = IndiceLocal()
    url_oficial = os.getenv("NANDA_OFICIAL_URL")
    return IndiceNandaOficial(url_oficial, local) if url_oficial else local


app = FastAPI(title="Vigia - Indice NANDA", version="0.1.0")
indice = crear_indice()


@app.get("/health")
def salud() -> dict:
    return {"estado": "ok"}


@app.post("/register", status_code=201)
def registrar(firmadas: AgentFactsFirmadas) -> dict:
    if not verificar(firmadas):
        raise HTTPException(400, "Firma Ed25519 invalida")
    try:
        indice.registrar(firmadas)
    except ClaveNoCoincide as e:
        raise HTTPException(409, str(e)) from e
    return {"id": firmadas.facts.id, "registrado": True}


@app.get("/resolve/{agent_id}", response_model=AgentFactsFirmadas)
def resolver(agent_id: str) -> AgentFactsFirmadas:
    firmadas = indice.resolver(agent_id)
    if firmadas is None:
        raise HTTPException(404, f"Agente {agent_id} no registrado")
    return firmadas


@app.get("/agents", response_model=list[AgentFactsFirmadas])
def listar() -> list[AgentFactsFirmadas]:
    return indice.listar()
