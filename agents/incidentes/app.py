"""Agente de incidentes: busca casos pasados similares filtrando columnas estructuradas (sin embeddings)."""

import asyncio
import json
import os
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, Request

from agents.comun import llm
from agents.comun.nanda import PublicadorFacts
from agents.incidentes.repo import RepoMemoria, RepoPostgres, semilla
from contracts.modelos import CasoIncidente, ConsultaIncidentes, RegistroIncidente, RespuestaIncidentes
from contracts.vocabulario import clasificar_labor

MIN_CASOS_CON_TURNO = 2
MAX_CASOS_DEVUELTOS = 5

SISTEMA_PATRON = (
    "Eres analista de seguridad minera en Peru. Resume en UNA oracion (maximo 35 palabras), en espanol "
    "neutro, el patron comun de los incidentes que recibes: riesgo critico, tipo de labor, turno y causas "
    "recurrentes. Usa solo los datos entregados; no inventes cifras ni recomendaciones."
)

publicador = PublicadorFacts(
    "vigia-incidentes",
    "Agente de incidentes",
    "Busca incidentes pasados similares a una tarea y resume su patron.",
    {"similares": "Casos similares por tipo de tarea, labor, turno y tipo de mineria",
     "registrar": "Agrega al historial el resultado de una tarea con novedad"},
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.getenv("DATABASE_URL")
    app.state.repo = RepoPostgres(url) if url else RepoMemoria(semilla())
    registro = asyncio.create_task(publicador.registrar_en_indice())
    yield
    registro.cancel()


app = FastAPI(title="Vigia - Agente de incidentes", version="0.1.0", lifespan=lifespan)
publicador.montar(app)


def obtener_repo(request: Request):
    return request.app.state.repo


def patron_determinista(filas: list[dict], labor_tipo: str, turno: str | None) -> str:
    riesgo, cantidad = Counter(f["riesgo_critico"] for f in filas).most_common(1)[0]
    causas = "; ".join(dict.fromkeys(f["causa_probable"].rstrip(".") for f in filas[:3]))
    en_turno = f" durante el turno {turno}" if turno else ""
    return (
        f"{len(filas)} casos similares, {cantidad} de {riesgo.replace('_', ' ')} en "
        f"{labor_tipo.replace('_', ' ')}{en_turno}. Causas: {causas}."
    )


def resumir_patron(filas: list[dict], labor_tipo: str, turno: str | None) -> str:
    if not filas:
        return "Sin incidentes similares registrados."
    casos = [
        {k: f[k] for k in ("turno", "riesgo_critico", "causa_probable", "potencial", "resumen_es")}
        for f in filas[:MAX_CASOS_DEVUELTOS]
    ]
    contexto = {"labor_tipo": labor_tipo, "casos": casos}
    texto = llm.redactar(SISTEMA_PATRON, json.dumps(contexto, ensure_ascii=False), max_tokens=2000)
    return texto or patron_determinista(filas, labor_tipo, turno)


@app.get("/health")
def salud() -> dict:
    return {"estado": "ok"}


@app.post("/incidentes/similares", response_model=RespuestaIncidentes)
def similares(consulta: ConsultaIncidentes, repo=Depends(obtener_repo)) -> RespuestaIncidentes:
    labor_tipo = clasificar_labor(consulta.tarea, consulta.labor)
    turno: str | None = consulta.turno
    filas = repo.buscar(consulta.tipo_mineria, consulta.tipo_tarea, labor_tipo, turno)
    if len(filas) < MIN_CASOS_CON_TURNO:
        turno = None
        filas = repo.buscar(consulta.tipo_mineria, consulta.tipo_tarea, labor_tipo, None)
    return RespuestaIncidentes(
        casos_similares=len(filas),
        patron=resumir_patron(filas, labor_tipo, turno),
        riesgo_potencial_max=filas[0]["potencial"] if filas else "ninguno",
        casos=[
            CasoIncidente(
                id=f["id"], resumen_es=f["resumen_es"],
                riesgo_critico=f["riesgo_critico"], causa_probable=f["causa_probable"],
            )
            for f in filas[:MAX_CASOS_DEVUELTOS]
        ],
    )


@app.post("/incidentes/registrar", status_code=201)
def registrar(registro: RegistroIncidente, repo=Depends(obtener_repo)) -> dict:
    fila = {
        "id": f"INC-{registro.petar_id}",
        "fecha": date.today().isoformat(),
        "tipo_mineria": registro.tipo_mineria,
        "tipo_tarea": registro.tipo_tarea,
        "labor_tipo": clasificar_labor(registro.tarea, registro.labor),
        "turno": registro.turno,
        "riesgo_critico": registro.riesgo_critico,
        "causa_probable": "Por investigar",
        "potencial": registro.potencial,
        "resumen_es": registro.resumen_es,
        "origen": "petar",
    }
    repo.registrar(fila)
    return {"id": fila["id"]}
