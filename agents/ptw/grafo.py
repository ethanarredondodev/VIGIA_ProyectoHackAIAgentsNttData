"""Grafo del agente PTW.

recibir_solicitud -> resolver_agentes (NANDA) -> [incidentes || area || gemelo]
-> calcular_riesgo (reglas) -> armar_checklist (controles_iperc)
-> redactar_explicacion (Claude Sonnet) -> esperar_firma (interrupt)
-> registrar_resultado (interrupt hasta que llega el resultado; vuelve al historial)
"""

import asyncio
import json
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agents.comun import llm
from agents.comun.sheets import TablaSheets
from agents.ptw import reglas_riesgo
from contracts.modelos import (
    ConsultaAptitud,
    ConsultaArea,
    ConsultaIncidentes,
    FirmaSupervisor,
    RegistroIncidente,
    ResultadoTarea,
    SolicitudPTW,
)
from contracts.vocabulario import clasificar_tarea

SISTEMA_EXPLICACION = (
    "Eres el asistente de seguridad de Vigia, un sistema de PETAR dinamico para mineria peruana "
    "(DS 024-2016-EM). Redacta para el supervisor una explicacion breve (maximo 110 palabras, espanol "
    "neutro, sin voseo) de por que el sistema propone la decision indicada. La decision y el nivel ya "
    "fueron calculados por reglas deterministas: no los cambies ni los cuestiones. Usa solo los datos "
    "entregados. No incluyas informacion clinica ni especules sobre la salud del trabajador; menciona la "
    "aptitud solo con su motivo visible. Termina recordando que la autorizacion requiere la firma del "
    "supervisor."
)

DECISIONES_LEGIBLES = {
    "autorizar": "autorizar",
    "autorizar_con_controles": "autorizar con controles",
    "reasignar": "reasignar",
}


class EstadoPTW(TypedDict, total=False):
    petar_id: str
    solicitud: dict
    tipo_tarea: str
    estado: str
    endpoints: dict
    incidentes: dict | None
    condiciones: dict | None
    aptitud: dict | None
    senales: dict
    evaluacion: dict
    checklist: list[dict]
    propuesta: dict
    explicacion: str
    firma: dict
    resultado: dict
    errores: Annotated[list[str], operator.add]


def explicacion_por_defecto(propuesta: dict) -> str:
    extras = ", ".join(propuesta["controles_extra"]) or "ninguno"
    return (
        f"Nivel {propuesta['nivel'].upper()}: se propone {DECISIONES_LEGIBLES[propuesta['decision']]}. "
        f"Motivos: {' '.join(propuesta['porque'])} Controles adicionales: {extras}. "
        "La autorización requiere la firma del supervisor."
    )


def construir_grafo(clientes, checkpointer, limites: TablaSheets, controles: TablaSheets):
    async def recibir_solicitud(estado: EstadoPTW) -> dict:
        solicitud = SolicitudPTW.model_validate(estado["solicitud"])
        return {"tipo_tarea": clasificar_tarea(solicitud.tarea), "estado": "evaluando"}

    async def resolver_agentes(estado: EstadoPTW) -> dict:
        return {"endpoints": await clientes.resolver()}

    async def consultar_incidentes(estado: EstadoPTW) -> dict:
        solicitud = estado["solicitud"]
        consulta = ConsultaIncidentes(
            tarea=solicitud["tarea"], tipo_tarea=estado["tipo_tarea"], labor=solicitud["labor"],
            turno=solicitud["turno"], tipo_mineria=solicitud["tipo_mineria"],
        )
        try:
            respuesta = await clientes.incidentes(estado["endpoints"]["incidentes"], consulta)
        except Exception as e:  # el agente caido no detiene el PETAR: las reglas lo tratan como dato faltante
            return {"incidentes": None, "errores": [f"incidentes: {e}"]}
        return {"incidentes": respuesta.model_dump()}

    async def consultar_area(estado: EstadoPTW) -> dict:
        try:
            respuesta = await clientes.area(estado["endpoints"]["area"], ConsultaArea(labor=estado["solicitud"]["labor"]))
        except Exception as e:
            return {"condiciones": None, "errores": [f"area: {e}"]}
        return {"condiciones": respuesta.model_dump()}

    async def consultar_gemelo(estado: EstadoPTW) -> dict:
        solicitud = estado["solicitud"]
        consulta = ConsultaAptitud(
            trabajador_id=solicitud["trabajador_id"], tipo_tarea=estado["tipo_tarea"], turno=solicitud["turno"],
            altitud_msnm=solicitud["altitud_msnm"], tipo_mineria=solicitud["tipo_mineria"],
            empleador=solicitud["empleador"],
        )
        try:
            respuesta = await clientes.gemelo(estado["endpoints"]["gemelo"], consulta)
        except Exception as e:
            return {"aptitud": None, "errores": [f"gemelo: {e}"]}
        return {"aptitud": respuesta.model_dump()}

    def calcular_riesgo(estado: EstadoPTW) -> dict:
        condiciones, aptitud, incidentes = estado.get("condiciones"), estado.get("aptitud"), estado.get("incidentes")
        senales = reglas_riesgo.construir_senales(
            estado["solicitud"], estado["tipo_tarea"], condiciones, aptitud, incidentes
        )
        evaluacion = reglas_riesgo.calcular_riesgo(senales, condiciones, aptitud, incidentes, limites.filas())
        return {"senales": senales, "evaluacion": evaluacion}

    def armar_checklist(estado: EstadoPTW) -> dict:
        checklist = reglas_riesgo.armar_checklist(estado["senales"], controles.filas())
        propuesta = reglas_riesgo.construir_propuesta(estado["evaluacion"], checklist)
        return {"checklist": checklist, "propuesta": propuesta.model_dump()}

    async def redactar_explicacion(estado: EstadoPTW) -> dict:
        contexto = {
            "solicitud": {k: v for k, v in estado["solicitud"].items() if k != "trabajador_id"},
            "propuesta": estado["propuesta"],
            "patron_incidentes": (estado.get("incidentes") or {}).get("patron"),
            "condiciones_labor": estado.get("condiciones"),
            "aptitud_motivo_visible": (estado.get("aptitud") or {}).get("motivo_visible"),
        }
        texto = await asyncio.to_thread(
            llm.redactar, SISTEMA_EXPLICACION, json.dumps(contexto, ensure_ascii=False)
        )
        return {"explicacion": texto or explicacion_por_defecto(estado["propuesta"]), "estado": "pendiente_firma"}

    def esperar_firma(estado: EstadoPTW) -> dict:
        firma = FirmaSupervisor.model_validate(interrupt({"espera": "firma", "petar_id": estado["petar_id"]}))
        if firma.accion == "aceptar" and not firma.controles_finales:
            firma.controles_finales = [item["control"] for item in estado["checklist"]]
        return {
            "firma": firma.model_dump(),
            "estado": reglas_riesgo.estado_tras_firma(estado["propuesta"], firma.model_dump()),
        }

    def tras_firma(estado: EstadoPTW) -> str:
        return "registrar_resultado" if estado["estado"] == "autorizado" else END

    async def registrar_resultado(estado: EstadoPTW) -> dict:
        resultado = ResultadoTarea.model_validate(interrupt({"espera": "resultado", "petar_id": estado["petar_id"]}))
        if resultado.resultado != "sin_novedad":
            solicitud = estado["solicitud"]
            casos = (estado.get("incidentes") or {}).get("casos") or []
            await clientes.registrar_incidente(
                estado["endpoints"]["incidentes"],
                RegistroIncidente(
                    petar_id=estado["petar_id"], tipo_tarea=estado["tipo_tarea"], labor=solicitud["labor"],
                    tarea=solicitud["tarea"], turno=solicitud["turno"], tipo_mineria=solicitud["tipo_mineria"],
                    riesgo_critico=casos[0]["riesgo_critico"] if casos else "otro",
                    potencial="alto" if resultado.resultado == "incidente" else "medio",
                    resumen_es=resultado.observacion or f"{resultado.resultado} durante {solicitud['tarea']}",
                ),
            )
        return {"resultado": resultado.model_dump(), "estado": "cerrado"}

    grafo = StateGraph(EstadoPTW)
    for nodo in (
        recibir_solicitud, resolver_agentes, consultar_incidentes, consultar_area, consultar_gemelo,
        calcular_riesgo, armar_checklist, redactar_explicacion, esperar_firma, registrar_resultado,
    ):
        grafo.add_node(nodo.__name__, nodo)

    consultas = ["consultar_incidentes", "consultar_area", "consultar_gemelo"]
    grafo.add_edge(START, "recibir_solicitud")
    grafo.add_edge("recibir_solicitud", "resolver_agentes")
    for consulta in consultas:
        grafo.add_edge("resolver_agentes", consulta)
    grafo.add_edge(consultas, "calcular_riesgo")
    grafo.add_edge("calcular_riesgo", "armar_checklist")
    grafo.add_edge("armar_checklist", "redactar_explicacion")
    grafo.add_edge("redactar_explicacion", "esperar_firma")
    grafo.add_conditional_edges("esperar_firma", tras_firma, ["registrar_resultado", END])
    grafo.add_edge("registrar_resultado", END)
    return grafo.compile(checkpointer=checkpointer)
