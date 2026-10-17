"""vigia-ptw: orquesta el PETAR dinamico.

El supervisor solo recibe el documento en caso de duda: verde se emite solo, ambar
(o trabajo de alto riesgo) va a firma, rojo se bloquea y se avisa al supervisor.
"""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agents.comun.nanda import PublicadorFacts
from agents.comun.sheets import TablaSheets
from agents.ptw.clientes import AgenteNoConfiable, ClientesAgentes, ClientesMock
from agents.ptw.grafo import construir_grafo
from agents.ptw.reglas_riesgo import validar_firma
from agents.ptw.repo import ESTADOS_BANDEJA, RepoPtwMemoria, RepoPtwPostgres, semilla
from contracts.modelos import (
    AvatarGemelo,
    FirmaSupervisor,
    ItemBandeja,
    PropuestaSupervisor,
    Ptw,
    ResultadoTarea,
    SolicitudAceptada,
    SolicitudPTW,
)

log = logging.getLogger(__name__)

# Campos del estado del grafo que se copian al registro que lee el front.
CAMPOS_REGISTRO = {
    "estado", "nanda", "propuesta", "petar", "explicacion", "checklist", "firma", "resultado",
}

publicador = PublicadorFacts(
    "vigia-ptw",
    "Orquestador PTW",
    "Arma el PETAR / IPERC continuo consultando a los agentes de incidentes, area y gemelo.",
    {"solicitud": "Evalua una solicitud de trabajo y emite, envia a revision o bloquea el PETAR"},
)


# Trazas de Langfuse: no salen el trabajador ni nada derivado de su salud o de su texto libre.
CAMPOS_SENSIBLES = {
    "trabajador_id", "trabajador_nombre", "nombre", "motivo_visible", "porque", "explicacion", "observacion",
    "resumen_es",
}


def enmascarar(*, data, **_):
    if isinstance(data, dict):
        return {k: "[reservado]" if k in CAMPOS_SENSIBLES else enmascarar(data=v) for k, v in data.items()}
    if isinstance(data, list):
        return [enmascarar(data=v) for v in data]
    return data


def montar_grafo(app: FastAPI, clientes, checkpointer) -> None:
    app.state.clientes = clientes
    app.state.grafo = construir_grafo(clientes, checkpointer, TablaSheets("limites_area"), TablaSheets("controles_iperc"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        from langfuse import Langfuse

        Langfuse(mask=enmascarar)  # el CallbackHandler de cada PTW reutiliza este cliente
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
        app.state.repo = RepoPtwPostgres(pool)
        await app.state.repo.preparar()
    else:
        checkpointer, app.state.repo = InMemorySaver(), RepoPtwMemoria(semilla())
    montar_grafo(app, clientes, checkpointer)
    registro = asyncio.create_task(publicador.registrar_en_indice())
    yield
    registro.cancel()
    if pool:
        await pool.close()


app = FastAPI(title="Vigía - Orquestador PTW", version="0.1.0", lifespan=lifespan)
origenes = [o.strip() for o in os.getenv("WEB_ORIGIN", "").split(",") if o.strip()]
if origenes:
    app.add_middleware(CORSMiddleware, allow_origins=origenes, allow_methods=["*"], allow_headers=["*"])
publicador.montar(app)


def configuracion(ptw_id: str) -> dict:
    config: dict = {"configurable": {"thread_id": ptw_id}}
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        from langfuse.langchain import CallbackHandler

        config["callbacks"] = [CallbackHandler()]
    return config


def aplicar(registro: dict, actualizacion: dict) -> None:
    for nodo, cambios in actualizacion.items():
        if nodo == "__interrupt__":
            if any(i.value.get("espera") == "firma" for i in cambios):
                registro["estado"] = "en_revision"
            continue
        for campo, valor in (cambios or {}).items():
            if campo == "consultas":
                registro["consultas"].update(valor)
            elif campo in CAMPOS_REGISTRO:
                registro[campo] = valor


async def procesar(app: FastAPI, ptw_id: str, entrada, evaluacion_inicial: bool) -> None:
    """Avanza el grafo y guarda el registro despues de cada nodo, para que el front vea cada consulta."""
    grafo, repo = app.state.grafo, app.state.repo
    try:
        async for actualizacion in grafo.astream(entrada, configuracion(ptw_id), stream_mode="updates"):
            registro = await repo.obtener(ptw_id)
            aplicar(registro, actualizacion)
            await repo.guardar(registro)
    except Exception as e:
        if not evaluacion_inicial:
            raise
        log.exception("Fallo la evaluacion de %s: se bloquea por seguridad", ptw_id)
        registro = await repo.obtener(ptw_id)
        registro["estado"] = "bloqueado"
        registro["propuesta"] = PropuestaSupervisor(
            decision="reasignar", nivel="rojo", requiere_supervisor=True,
            porque=[f"Error interno al evaluar la solicitud: {e}"], controles_extra=[],
            alternativa="Esperar: evaluar la tarea manualmente con el supervisor.",
        ).model_dump()
        await repo.guardar(registro)


def publico(registro: dict) -> Ptw:
    return Ptw.model_validate({k: registro[k] for k in Ptw.model_fields if k in registro})


async def registro_en(request: Request, ptw_id: str, estados: tuple[str, ...]) -> dict:
    registro = await request.app.state.repo.obtener(ptw_id)
    if registro is None:
        raise HTTPException(404, f"PTW {ptw_id} no existe")
    if registro["estado"] not in estados:
        raise HTTPException(409, f"PTW {ptw_id} esta en estado {registro['estado']}; se esperaba {' o '.join(estados)}")
    return registro


async def reanudar(request: Request, ptw_id: str, valor: dict) -> Ptw:
    try:
        await procesar(request.app, ptw_id, Command(resume=valor), evaluacion_inicial=False)
    except (httpx.HTTPError, AgenteNoConfiable) as e:
        raise HTTPException(502, f"Un agente no respondio o no es confiable: {e}") from e
    return publico(await request.app.state.repo.obtener(ptw_id))


@app.get("/health")
def salud() -> dict:
    return {"estado": "ok", "mock_mode": os.getenv("MOCK_MODE", "false")}


@app.post("/ptw/solicitud", response_model=SolicitudAceptada, status_code=202)
async def solicitud(cuerpo: SolicitudPTW, request: Request, tareas: BackgroundTasks) -> SolicitudAceptada:
    trabajador = await request.app.state.repo.trabajador(cuerpo.trabajador_id)
    if trabajador is None:
        raise HTTPException(404, f"Trabajador {cuerpo.trabajador_id} no registrado")
    if trabajador["estado"] != "activo":
        raise HTTPException(409, f"Trabajador {cuerpo.trabajador_id} no esta activo")
    ptw_id = f"PTW-{uuid.uuid4().hex[:8].upper()}"
    await request.app.state.repo.guardar({
        "ptw_id": ptw_id,
        "estado": "procesando",
        "solicitud": cuerpo.model_dump(),
        "trabajador_nombre": f"{trabajador['nombres']} {trabajador['apellidos']}",
        "consultas": {agente: {"estado": "pendiente"} for agente in ("incidentes", "area", "gemelo")},
        "nanda": [],
        "creado_en": datetime.now(timezone.utc).isoformat(),
    })
    entrada = {"ptw_id": ptw_id, "solicitud": cuerpo.model_dump()}
    tareas.add_task(procesar, request.app, ptw_id, entrada, True)
    return SolicitudAceptada(ptw_id=ptw_id)


@app.get("/ptw/bandeja", response_model=list[ItemBandeja])
async def bandeja(request: Request) -> list[ItemBandeja]:
    registros = await request.app.state.repo.listar(estados=ESTADOS_BANDEJA)
    return [
        ItemBandeja(
            ptw_id=r["ptw_id"],
            nivel=r["propuesta"]["nivel"],
            requiere_supervisor=r["propuesta"]["requiere_supervisor"],
            trabajador_nombre=r.get("trabajador_nombre") or r["solicitud"]["trabajador_id"],
            tarea=r["solicitud"]["tarea"],
            labor=r["solicitud"]["labor"],
            turno=r["solicitud"]["turno"],
            creado_en=r["creado_en"],
            tipo="revision" if r["estado"] == "en_revision" else "aviso",
        )
        for r in registros
    ]


@app.get("/ptw/{ptw_id}", response_model=Ptw, response_model_exclude_unset=True)
async def obtener(ptw_id: str, request: Request) -> Ptw:
    registro = await request.app.state.repo.obtener(ptw_id)
    if registro is None:
        raise HTTPException(404, f"PTW {ptw_id} no existe")
    return publico(registro)


@app.get("/ptw", response_model=list[Ptw], response_model_exclude_unset=True)
async def listar(request: Request, trabajador_id: str | None = None) -> list[Ptw]:
    return [publico(r) for r in await request.app.state.repo.listar(trabajador_id=trabajador_id)]


@app.post("/ptw/{ptw_id}/firma", response_model=Ptw, response_model_exclude_unset=True)
async def firma(ptw_id: str, cuerpo: FirmaSupervisor, request: Request) -> Ptw:
    await registro_en(request, ptw_id, ("en_revision",))
    error = validar_firma(cuerpo)
    if error:
        raise HTTPException(422, error)
    return await reanudar(request, ptw_id, cuerpo.model_dump())


@app.post("/ptw/{ptw_id}/inicio", response_model=Ptw, response_model_exclude_unset=True)
async def inicio(ptw_id: str, request: Request) -> Ptw:
    """El trabajador confirma que empezo la tarea con el PETAR emitido o autorizado."""
    registro = await registro_en(request, ptw_id, ("emitido", "autorizado_con_controles"))
    registro["estado"] = "en_ejecucion"
    await request.app.state.repo.guardar(registro)
    return publico(registro)


@app.post("/ptw/{ptw_id}/resultado", response_model=Ptw, response_model_exclude_unset=True)
async def resultado(ptw_id: str, cuerpo: ResultadoTarea, request: Request) -> Ptw:
    await registro_en(request, ptw_id, ("emitido", "autorizado_con_controles", "en_ejecucion"))
    return await reanudar(request, ptw_id, cuerpo.model_dump())


@app.get("/trabajadores/{trabajador_id}/avatar", response_model=AvatarGemelo)
async def avatar(trabajador_id: str, request: Request) -> AvatarGemelo:
    clientes = request.app.state.clientes
    destinos, _ = await clientes.resolver()
    try:
        return await clientes.avatar(destinos["gemelo"], trabajador_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Gemelo: {e.response.text}") from e
    except (httpx.HTTPError, AgenteNoConfiable) as e:
        raise HTTPException(502, f"El gemelo no respondio o no es confiable: {e}") from e
