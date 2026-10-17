"""Gemelo del trabajador (ZONA CLINICA).

Responde si la persona esta apta hoy para la tarea y entrega su avatar visual.
Nunca devuelve detalle clinico: `diagnostico` es siempre null y el avatar no
trae datos clinicos ni fotos. En Cloud Run este servicio no es publico: solo
vigia-ptw lo invoca mediante IAM.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request

from agents.comun.nanda import PublicadorFacts
from agents.comun.reglas import cumple
from agents.comun.sheets import TablaSheets, activas
from agents.gemelo.energia import calcular_energia, total_rotacion
from agents.gemelo.repo import RepoMemoria, RepoPostgres, semilla
from contracts.agent_facts import ZONA_CLINICA
from contracts.modelos import AvatarGemelo, ConsultaAptitud, EstadoVisual, RespuestaAptitud

GRAVEDAD = {"apto": 0, "apto_con_observaciones": 1, "no_apto": 2}
SIN_GEMELO = "Sin evaluación vigente en la zona clínica: acudir a salud ocupacional"
SIN_OBSERVACIONES = "Sin observaciones para la tarea"
VARIABLES_DEL_GEMELO = ("sueno_h", "dia_rotacion", "regimen_turno", "exposicion_silice")

reglas_clinicas = TablaSheets("reglas_zona_clinica")

publicador = PublicadorFacts(
    "vigia-gemelo",
    "Gemelo del trabajador",
    "Zona clinica aislada: indica si un trabajador esta apto hoy para una tarea, sin detalle clinico.",
    {"aptitud": "apto | apto_con_observaciones | no_apto con un motivo visible",
     "avatar": "Estado visual del trabajador (energia, rotacion, exposicion) sin datos clinicos"},
    claims=ZONA_CLINICA,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.getenv("DATABASE_URL")
    app.state.repo = RepoPostgres(url) if url else RepoMemoria(semilla())
    registro = asyncio.create_task(publicador.registrar_en_indice())
    yield
    registro.cancel()


app = FastAPI(
    title="Vigía - Gemelo del trabajador (zona clínica)",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
publicador.montar(app)


def obtener_repo(request: Request):
    return request.app.state.repo


def evaluar_aptitud(gemelo: dict | None, trabajador_id: str, contexto: dict, reglas: list[dict]) -> RespuestaAptitud:
    """`contexto` son las variables de la tarea; sin tarea (avatar) solo aplican las reglas del trabajador."""
    if gemelo is None:
        return RespuestaAptitud(trabajador_id=trabajador_id, apto_para_tarea="no_apto", motivo_visible=SIN_GEMELO)
    restringidas = gemelo["datos_clinicos"].get("tareas_restringidas", [])
    senales = {
        **contexto, **{k: gemelo[k] for k in VARIABLES_DEL_GEMELO},
        "tarea_restringida": "si" if contexto.get("tipo_tarea") in restringidas else "no",
    }
    disparadas = [r for r in activas(reglas) if cumple(senales, r["variable"], r["operador"], r["umbral"])]
    if not disparadas:
        return RespuestaAptitud(trabajador_id=trabajador_id, apto_para_tarea="apto", motivo_visible=SIN_OBSERVACIONES)
    peor = max(disparadas, key=lambda r: GRAVEDAD[r["resultado"]])["resultado"]
    motivos = dict.fromkeys(r["motivo_visible"] for r in disparadas if r["resultado"] == peor)
    return RespuestaAptitud(trabajador_id=trabajador_id, apto_para_tarea=peor, motivo_visible="; ".join(motivos))


@app.get("/health")
def salud() -> dict:
    return {"estado": "ok"}


@app.post("/gemelo/aptitud", response_model=RespuestaAptitud)
def aptitud(consulta: ConsultaAptitud, repo=Depends(obtener_repo)) -> RespuestaAptitud:
    gemelo = repo.obtener(consulta.trabajador_id)
    return evaluar_aptitud(gemelo, consulta.trabajador_id, consulta.model_dump(), reglas_clinicas.filas())


@app.get("/gemelo/{trabajador_id}/avatar", response_model=AvatarGemelo)
def avatar(trabajador_id: str, repo=Depends(obtener_repo)) -> AvatarGemelo:
    gemelo = repo.obtener(trabajador_id)
    if gemelo is None:
        raise HTTPException(404, f"Trabajador {trabajador_id} sin gemelo")
    aptitud = evaluar_aptitud(gemelo, trabajador_id, {}, reglas_clinicas.filas())
    total = total_rotacion(gemelo["regimen_turno"])
    return AvatarGemelo(
        trabajador_id=trabajador_id,
        nombre=gemelo["nombre"],
        cargo=gemelo["cargo"],
        empresa=gemelo["empresa"],
        empleador=gemelo["empleador"],
        seed=gemelo["seed"],
        color_casco=gemelo["color_casco"],
        estado_visual=EstadoVisual(
            apto_para_tarea=aptitud.apto_para_tarea,
            motivo_visible=aptitud.motivo_visible,
            energia=calcular_energia(gemelo["sueno_h"], gemelo["dia_rotacion"], total),
            dia_rotacion=gemelo["dia_rotacion"],
            total_rotacion=total,
            exposicion_nivel=gemelo["exposicion_silice"],
            historial_energia=gemelo["historial_energia"],
        ),
    )
