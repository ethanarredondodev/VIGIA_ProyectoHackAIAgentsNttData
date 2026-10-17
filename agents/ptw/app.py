"""Agente PTW: orquesta el PETAR dinamico. Un humano siempre firma."""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agents.comun.nanda import PublicadorFacts
from agents.comun.sheets import TablaSheets
from agents.ptw.clientes import ClientesAgentes, ClientesMock
from agents.ptw.grafo import construir_grafo
from agents.ptw.reglas_riesgo import validar_firma
from agents.ptw.repo import RepoPetarMemoria, RepoPetarPostgres
from contracts.modelos import FirmaSupervisor, Insumos, Petar, ResultadoTarea, SolicitudPTW

publicador = PublicadorFacts(
    "vigia-ptw",
    "Orquestador PTW",
    "Arma el PETAR / IPERC continuo consultando a los agentes de incidentes, area y gemelo.",
    {"solicitud": "Evalua una solicitud de trabajo y propone autorizar, autorizar con controles o reasignar"},
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.getenv("DATABASE_URL")
    clientes = ClientesMock() if os.getenv("MOCK_MODE", "false").lower() == "true" else ClientesAgentes()
    pool = None
    if url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        pool = AsyncConnectionPool(
            url, open=False, kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}
        )
        await pool.open()
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        repo = RepoPetarPostgres(pool)
        await repo.preparar()
    else:
        checkpointer, repo = InMemorySaver(), RepoPetarMemoria()
    app.state.clientes = clientes
    app.state.repo = repo
    app.state.grafo = construir_grafo(clientes, checkpointer, TablaSheets("limites_area"), TablaSheets("controles_iperc"))
    registro = asyncio.create_task(publicador.registrar_en_indice())
    yield
    registro.cancel()
    if pool:
        await pool.close()


app = FastAPI(title="Vigia - Orquestador PTW", version="0.1.0", lifespan=lifespan)
publicador.montar(app)


def configuracion(petar_id: str) -> dict:
    config: dict = {"configurable": {"thread_id": petar_id}}
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        from langfuse.langchain import CallbackHandler

        config["callbacks"] = [CallbackHandler()]
    return config


async def avanzar(request: Request, petar_id: str, entrada, creado_en: datetime) -> Petar:
    grafo = request.app.state.grafo
    await grafo.ainvoke(entrada, configuracion(petar_id))
    valores = (await grafo.aget_state({"configurable": {"thread_id": petar_id}})).values
    petar = Petar(
        id=petar_id,
        estado=valores.get("estado", "evaluando"),
        solicitud=valores["solicitud"],
        propuesta=valores.get("propuesta"),
        checklist=valores.get("checklist", []),
        explicacion=valores.get("explicacion", ""),
        insumos=Insumos(
            incidentes=valores.get("incidentes"),
            condiciones=valores.get("condiciones"),
            aptitud=valores.get("aptitud"),
        ),
        errores=valores.get("errores", []),
        firma=valores.get("firma"),
        resultado=valores.get("resultado"),
        creado_en=creado_en,
        actualizado_en=datetime.now(timezone.utc),
    )
    await request.app.state.repo.guardar(petar)
    return petar


async def petar_existente(request: Request, petar_id: str, estado_esperado: str) -> Petar:
    petar = await request.app.state.repo.obtener(petar_id)
    if petar is None:
        raise HTTPException(404, f"PETAR {petar_id} no existe")
    if petar.estado != estado_esperado:
        raise HTTPException(409, f"PETAR {petar_id} esta en estado {petar.estado}, se esperaba {estado_esperado}")
    return petar


@app.get("/health")
def salud() -> dict:
    return {"estado": "ok", "mock_mode": os.getenv("MOCK_MODE", "false")}


@app.post("/ptw/solicitud", response_model=Petar)
async def solicitud(cuerpo: SolicitudPTW, request: Request) -> Petar:
    petar_id = f"PTW-{uuid.uuid4().hex[:8].upper()}"
    entrada = {"petar_id": petar_id, "solicitud": cuerpo.model_dump(), "errores": []}
    return await avanzar(request, petar_id, entrada, datetime.now(timezone.utc))


@app.post("/ptw/{petar_id}/firma", response_model=Petar)
async def firma(petar_id: str, cuerpo: FirmaSupervisor, request: Request) -> Petar:
    petar = await petar_existente(request, petar_id, "pendiente_firma")
    error = validar_firma(petar.propuesta, cuerpo)
    if error:
        raise HTTPException(422, error)
    return await avanzar(request, petar_id, Command(resume=cuerpo.model_dump()), petar.creado_en)


@app.post("/ptw/{petar_id}/resultado", response_model=Petar)
async def resultado(petar_id: str, cuerpo: ResultadoTarea, request: Request) -> Petar:
    petar = await petar_existente(request, petar_id, "autorizado")
    return await avanzar(request, petar_id, Command(resume=cuerpo.model_dump()), petar.creado_en)


@app.get("/ptw/{petar_id}", response_model=Petar)
async def obtener(petar_id: str, request: Request) -> Petar:
    petar = await request.app.state.repo.obtener(petar_id)
    if petar is None:
        raise HTTPException(404, f"PETAR {petar_id} no existe")
    return petar


@app.get("/ptw", response_model=list[Petar])
async def listar(request: Request, estado: str | None = None, trabajador_id: str | None = None) -> list[Petar]:
    return await request.app.state.repo.listar(estado, trabajador_id)
