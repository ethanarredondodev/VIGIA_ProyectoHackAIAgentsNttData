"""Agente de area: condiciones actuales de la labor (gases, O2, ventilacion, ruido, ultimo desatado)."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request

from agents.area.repo import RepoMemoria, RepoPostgres, semilla
from agents.comun.nanda import PublicadorFacts
from contracts.modelos import ConsultaArea, RespuestaArea

publicador = PublicadorFacts(
    "vigia-area",
    "Agente de area",
    "Entrega las condiciones actuales de una labor minera.",
    {"condiciones": "CO, O2, ventilacion, ruido y horas desde el ultimo desatado"},
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.getenv("DATABASE_URL")
    app.state.repo = RepoPostgres(url) if url else RepoMemoria(semilla())
    registro = asyncio.create_task(publicador.registrar_en_indice())
    yield
    registro.cancel()


app = FastAPI(title="Vigia - Agente de area", version="0.1.0", lifespan=lifespan)
publicador.montar(app)


def obtener_repo(request: Request):
    return request.app.state.repo


@app.get("/health")
def salud() -> dict:
    return {"estado": "ok"}


@app.post("/area/condiciones", response_model=RespuestaArea)
def condiciones(consulta: ConsultaArea, repo=Depends(obtener_repo)) -> RespuestaArea:
    fila = repo.obtener(consulta.labor)
    if fila is None:
        raise HTTPException(404, f"Labor {consulta.labor} sin mediciones registradas")
    return RespuestaArea.model_validate({k: fila[k] for k in RespuestaArea.model_fields})
