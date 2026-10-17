"""Gemelo del trabajador (ZONA CLINICA).

Responde solo si la persona esta apta hoy para la tarea. Nunca devuelve detalle
clinico: `diagnostico` es siempre null y no existe endpoint de detalle.
En Cloud Run este servicio no es publico: solo `ptw` lo invoca mediante IAM.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request

from agents.comun.nanda import PublicadorFacts
from agents.comun.reglas import cumple
from agents.comun.sheets import TablaSheets, activas
from agents.gemelo.repo import RepoMemoria, RepoPostgres, semilla
from contracts.modelos import ConsultaAptitud, RespuestaAptitud

GRAVEDAD = {"apto": 0, "apto_con_observaciones": 1, "no_apto": 2}
SIN_GEMELO = "Sin evaluación vigente en la zona clínica: acudir a salud ocupacional"
SIN_OBSERVACIONES = "Sin observaciones para la tarea"
VARIABLES_DEL_GEMELO = ("sueno_h", "dia_rotacion", "regimen_turno", "exposicion_silice")

reglas_clinicas = TablaSheets("reglas_zona_clinica")

publicador = PublicadorFacts(
    "vigia-gemelo",
    "Gemelo del trabajador",
    "Zona clinica aislada: indica si un trabajador esta apto hoy para una tarea, sin detalle clinico.",
    {"aptitud": "apto | apto_con_observaciones | no_apto con un motivo visible"},
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.getenv("DATABASE_URL")
    app.state.repo = RepoPostgres(url) if url else RepoMemoria(semilla())
    registro = asyncio.create_task(publicador.registrar_en_indice())
    yield
    registro.cancel()


app = FastAPI(
    title="Vigia - Gemelo del trabajador (zona clinica)",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
publicador.montar(app)


def obtener_repo(request: Request):
    return request.app.state.repo


def evaluar_aptitud(gemelo: dict | None, consulta: ConsultaAptitud, reglas: list[dict]) -> RespuestaAptitud:
    if gemelo is None:
        return RespuestaAptitud(
            trabajador_id=consulta.trabajador_id, apto_para_tarea="no_apto", motivo_visible=SIN_GEMELO
        )
    senales = {**consulta.model_dump(), **{k: gemelo[k] for k in VARIABLES_DEL_GEMELO}}
    disparadas = [r for r in activas(reglas) if cumple(senales, r["variable"], r["operador"], r["umbral"])]
    if not disparadas:
        return RespuestaAptitud(
            trabajador_id=consulta.trabajador_id, apto_para_tarea="apto", motivo_visible=SIN_OBSERVACIONES
        )
    peor = max(disparadas, key=lambda r: GRAVEDAD[r["resultado"]])["resultado"]
    motivos = dict.fromkeys(r["motivo_visible"] for r in disparadas if r["resultado"] == peor)
    return RespuestaAptitud(
        trabajador_id=consulta.trabajador_id, apto_para_tarea=peor, motivo_visible="; ".join(motivos)
    )


@app.get("/health")
def salud() -> dict:
    return {"estado": "ok"}


@app.post("/gemelo/aptitud", response_model=RespuestaAptitud)
def aptitud(consulta: ConsultaAptitud, repo=Depends(obtener_repo)) -> RespuestaAptitud:
    return evaluar_aptitud(repo.obtener(consulta.trabajador_id), consulta, reglas_clinicas.filas())
