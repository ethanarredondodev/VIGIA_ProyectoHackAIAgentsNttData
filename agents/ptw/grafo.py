"""Grafo del agente PTW. El supervisor solo recibe el documento en caso de duda.

recibir_solicitud -> resolver_agentes (NANDA) -> [incidentes || area || gemelo]
-> calcular_riesgo (reglas) -> armar_checklist (controles_iperc)
-> redactar_explicacion (Claude Sonnet) -> enrutar_por_nivel:
     verde sin alto riesgo     -> emitir_petar
     ambar o alto riesgo       -> esperar_firma (interrupt)
     rojo                      -> bloquear_y_avisar (sin pedir firma) -> fin
-> registrar_resultado (interrupt hasta que llega el resultado; vuelve al historial)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
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

log = logging.getLogger(__name__)

SISTEMA_EXPLICACION = (
    "Eres el asistente de seguridad de Vigía, un sistema de PETAR dinamico para mineria peruana "
    "(DS 024-2016-EM). Redacta una explicacion breve (maximo 110 palabras, espanol neutro, sin voseo) de "
    "por que el sistema propone la decision indicada. La decision y el nivel ya fueron calculados por "
    "reglas deterministas: no los cambies ni los cuestiones. Usa solo los datos entregados. Los datos de "
    "salud del trabajador no se te entregan: si un motivo dice `[dato de salud reservado]`, indica solo que "
    "la aptitud tiene observaciones que el supervisor ve en el detalle, sin especular. "
    "Si `requiere_supervisor` es verdadero o el nivel es ambar, termina indicando que el "
    "supervisor debe revisar y firmar; si el nivel es rojo, que la tarea queda bloqueada."
)

RESERVADO = "[dato de salud reservado]"

DECISIONES_LEGIBLES = {
    "autorizar": "autorizar",
    "autorizar_con_controles": "autorizar con controles",
    "reasignar": "reasignar o esperar",
}


def _combinar(actual: dict | None, nuevo: dict) -> dict:
    return {**(actual or {}), **nuevo}


class EstadoPTW(TypedDict, total=False):
    ptw_id: str
    solicitud: dict
    tipo_tarea: str
    estado: str
    endpoints: dict
    nanda: list[dict]
    consultas: Annotated[dict, _combinar]
    senales: dict
    evaluacion: dict
    checklist: list[dict]
    propuesta: dict
    explicacion: str
    firma: dict
    petar: dict
    resultado: dict


def explicacion_por_defecto(propuesta: dict) -> str:
    extras = ", ".join(propuesta["controles_extra"]) or "ninguno"
    if propuesta["nivel"] == "rojo":
        cierre = "La tarea queda bloqueada y se avisó al supervisor."
    elif propuesta["nivel"] == "ambar" or propuesta["requiere_supervisor"]:
        cierre = "El supervisor debe revisar y firmar el PETAR."
    else:
        cierre = "El PETAR se emite automáticamente con su checklist IPERC."
    return (
        f"Nivel {propuesta['nivel'].upper()}: se propone {DECISIONES_LEGIBLES[propuesta['decision']]}. "
        f"Motivos: {' '.join(propuesta['porque'])} Controles adicionales: {extras}. {cierre}"
    )


def nuevo_petar(ptw_id: str, checklist: list[str], firmado_por: str | None) -> dict:
    ahora = datetime.now(timezone.utc)
    return {
        "numero": f"PETAR-{ahora:%Y%m%d}-{ptw_id.removeprefix('PTW-')}",
        "checklist": checklist,
        "firmado_por": firmado_por,
        "emitido_en": ahora.isoformat(),
    }


def datos_de(estado: dict, agente: str) -> dict | None:
    consulta = (estado.get("consultas") or {}).get(agente) or {}
    return consulta.get("data") if consulta.get("estado") == "ok" else None


def construir_grafo(clientes, checkpointer, limites: TablaSheets, controles: TablaSheets):
    async def consultar(agente: str, llamada) -> dict:
        try:
            respuesta, evidencia = await llamada
        except Exception as e:  # un agente caido o no confiable no detiene el PETAR: las reglas lo tratan como dato faltante
            log.warning("Consulta a %s fallida: %s", agente, e)
            return {"consultas": {agente: {"estado": "error"}}}
        return {"consultas": {agente: {"estado": "ok", "data": respuesta.model_dump(), "evidencia": evidencia}}}

    async def recibir_solicitud(estado: EstadoPTW) -> dict:
        solicitud = SolicitudPTW.model_validate(estado["solicitud"])
        return {"tipo_tarea": clasificar_tarea(solicitud.tarea), "estado": "procesando"}

    async def resolver_agentes(estado: EstadoPTW) -> dict:
        endpoints, nanda = await clientes.resolver()
        return {"endpoints": endpoints, "nanda": nanda}

    async def consultar_incidentes(estado: EstadoPTW) -> dict:
        solicitud = estado["solicitud"]
        consulta = ConsultaIncidentes(
            tarea=solicitud["tarea"], tipo_tarea=estado["tipo_tarea"], labor=solicitud["labor"],
            turno=solicitud["turno"], tipo_mineria=solicitud["tipo_mineria"],
        )
        return await consultar("incidentes", clientes.incidentes(estado["endpoints"]["incidentes"], consulta))

    async def consultar_area(estado: EstadoPTW) -> dict:
        consulta = ConsultaArea(labor=estado["solicitud"]["labor"])
        return await consultar("area", clientes.area(estado["endpoints"]["area"], consulta))

    async def consultar_gemelo(estado: EstadoPTW) -> dict:
        solicitud = estado["solicitud"]
        consulta = ConsultaAptitud(
            trabajador_id=solicitud["trabajador_id"], tipo_tarea=estado["tipo_tarea"], turno=solicitud["turno"],
            altitud_msnm=solicitud["altitud_msnm"], tipo_mineria=solicitud["tipo_mineria"],
            empleador=solicitud["empleador"],
        )
        return await consultar("gemelo", clientes.gemelo(estado["endpoints"]["gemelo"], consulta))

    def calcular_riesgo(estado: EstadoPTW) -> dict:
        condiciones, aptitud, incidentes = datos_de(estado, "area"), datos_de(estado, "gemelo"), datos_de(estado, "incidentes")
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
        # Zona clinica: Claude no recibe ni el trabajador ni el motivo de su aptitud.
        motivo = (datos_de(estado, "gemelo") or {}).get("motivo_visible")
        porque = [p.replace(motivo, RESERVADO) if motivo else p for p in estado["propuesta"]["porque"]]
        contexto = {
            "solicitud": {k: v for k, v in estado["solicitud"].items() if k != "trabajador_id"},
            "propuesta": {**estado["propuesta"], "porque": porque},
            "patron_incidentes": (datos_de(estado, "incidentes") or {}).get("patron"),
            "condiciones_labor": datos_de(estado, "area"),
        }
        texto = await asyncio.to_thread(
            llm.redactar, SISTEMA_EXPLICACION, json.dumps(contexto, ensure_ascii=False)
        )
        return {"explicacion": texto or explicacion_por_defecto(estado["propuesta"])}

    def enrutar_por_nivel(estado: EstadoPTW) -> str:
        propuesta = estado["propuesta"]
        if propuesta["nivel"] == "rojo":
            return "bloquear_y_avisar"
        if propuesta["nivel"] == "ambar" or propuesta["requiere_supervisor"]:
            return "esperar_firma"
        return "emitir_petar"

    def emitir_petar(estado: EstadoPTW) -> dict:
        controles_finales = [item["control"] for item in estado["checklist"]]
        return {"estado": "emitido", "petar": nuevo_petar(estado["ptw_id"], controles_finales, None)}

    def bloquear_y_avisar(estado: EstadoPTW) -> dict:
        log.warning("PTW %s bloqueado (rojo): aviso al supervisor", estado["ptw_id"])
        return {"estado": "bloqueado"}

    def esperar_firma(estado: EstadoPTW) -> dict:
        firma = FirmaSupervisor.model_validate(interrupt({"espera": "firma", "ptw_id": estado["ptw_id"]}))
        if firma.accion == "rechazar":
            return {"firma": firma.model_dump(), "estado": "rechazado"}
        base = [item["control"] for item in estado["checklist"] if item["origen"] == "base"]
        extras = (
            firma.controles_finales if firma.accion == "ajustar"
            else [item["control"] for item in estado["checklist"] if item["origen"] == "extra"]
        )
        controles_finales = list(dict.fromkeys(base + extras))
        return {
            "firma": firma.model_dump(),
            "estado": "autorizado_con_controles",
            "petar": nuevo_petar(estado["ptw_id"], controles_finales, firma.supervisor),
        }

    def tras_firma(estado: EstadoPTW) -> str:
        return "registrar_resultado" if estado["estado"] == "autorizado_con_controles" else END

    async def registrar_resultado(estado: EstadoPTW) -> dict:
        resultado = ResultadoTarea.model_validate(interrupt({"espera": "resultado", "ptw_id": estado["ptw_id"]}))
        if resultado.resultado != "sin_novedad":
            solicitud = estado["solicitud"]
            casos = (datos_de(estado, "incidentes") or {}).get("casos") or []
            await clientes.registrar_incidente(
                estado["endpoints"]["incidentes"],
                RegistroIncidente(
                    petar_id=estado["ptw_id"], tipo_tarea=estado["tipo_tarea"], labor=solicitud["labor"],
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
        calcular_riesgo, armar_checklist, redactar_explicacion, emitir_petar, esperar_firma,
        bloquear_y_avisar, registrar_resultado,
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
    grafo.add_conditional_edges(
        "redactar_explicacion", enrutar_por_nivel, ["emitir_petar", "esperar_firma", "bloquear_y_avisar"]
    )
    grafo.add_edge("emitir_petar", "registrar_resultado")
    grafo.add_conditional_edges("esperar_firma", tras_firma, ["registrar_resultado", END])
    grafo.add_edge("bloquear_y_avisar", END)
    grafo.add_edge("registrar_resultado", END)
    return grafo.compile(checkpointer=checkpointer)
