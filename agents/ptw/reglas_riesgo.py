"""Calculo determinista del nivel de riesgo, del checklist IPERC y de si requiere supervisor.

El nivel verde/ambar/rojo lo deciden estas reglas con base legal (limites_area.csv,
controles_iperc.csv); el LLM nunca interviene aqui. Si algun control aplicable tiene
trabajo_alto_riesgo = si (DS 024-2016-EM arts. 129-130), el PETAR va a firma aunque sea verde.
"""

from agents.comun.reglas import comparar, cumple, parsear_disparador
from agents.comun.sheets import activas
from contracts.modelos import FirmaSupervisor, ItemChecklist, PropuestaSupervisor

GRAVEDAD = {"verde": 0, "ambar": 1, "rojo": 2}
DECISION = {"verde": "autorizar", "ambar": "autorizar_con_controles", "rojo": "reasignar"}

# tipo en limites_area.csv -> (nivel si se incumple, operador que detecta el incumplimiento, texto)
TIPOS_LIMITE = {
    "max_rojo": ("rojo", ">", "supera el máximo de"),
    "max_ambar": ("ambar", ">", "supera el máximo de"),
    "min_rojo": ("rojo", "<", "está por debajo del mínimo de"),
    "min_ambar": ("ambar", "<", "está por debajo del mínimo de"),
    "igual_rojo": ("rojo", "!=", "no cumple lo requerido:"),
}

NOMBRES = {
    "co_ppm": "CO",
    "o2_pct": "O2",
    "ruido_dBA": "Ruido",
    "ultimo_desatado_h": "Último desatado",
    "ventilacion": "Ventilación",
}

UMBRAL_CASOS_SIMILARES = 3
POTENCIALES_GRAVES = {"alto", "critico"}


def _fmt(valor) -> str:
    return f"{valor:g}" if isinstance(valor, float | int) else str(valor)


def construir_senales(
    solicitud: dict, tipo_tarea: str, condiciones: dict | None, aptitud: dict | None, incidentes: dict | None
) -> dict:
    senales = {**solicitud, "tipo_tarea": tipo_tarea}
    if condiciones:
        senales.update({k: v for k, v in condiciones.items() if k != "labor"})
    senales["apto_para_tarea"] = aptitud["apto_para_tarea"] if aptitud else None
    senales["casos_similares"] = incidentes["casos_similares"] if incidentes else None
    senales["riesgo_potencial_max"] = incidentes["riesgo_potencial_max"] if incidentes else None
    return senales


def calcular_riesgo(
    senales: dict, condiciones: dict | None, aptitud: dict | None, incidentes: dict | None, limites: list[dict]
) -> dict:
    nivel = "verde"
    porque: list[str] = []
    causas_rojo: set[str] = set()

    def elevar(nuevo: str, motivo: str, causa: str) -> None:
        nonlocal nivel
        if GRAVEDAD[nuevo] > GRAVEDAD[nivel]:
            nivel = nuevo
        if nuevo == "rojo":
            causas_rojo.add(causa)
        porque.append(motivo)

    if condiciones is None:
        elevar("rojo", "No se obtuvieron las condiciones de la labor: no se puede verificar la atmósfera.", "area")
    else:
        for limite in activas(limites):
            if limite["tipo_mineria"] not in ("todas", senales["tipo_mineria"]):
                continue
            nivel_limite, operador, texto = TIPOS_LIMITE[limite["tipo"]]
            valor = senales.get(limite["agente"])
            if valor is not None and comparar(valor, operador, limite["limite"]):
                unidad = f" {limite['unidad']}" if limite["unidad"] else ""
                elevar(
                    nivel_limite,
                    f"{NOMBRES.get(limite['agente'], limite['agente'])} {_fmt(valor)}{unidad} {texto} "
                    f"{limite['limite']}{unidad} ({limite['base_legal']}).",
                    "area",
                )

    if aptitud is None:
        elevar("rojo", "No se pudo confirmar la aptitud del trabajador en la zona clínica.", "aptitud")
    elif aptitud["apto_para_tarea"] == "no_apto":
        elevar("rojo", f"Trabajador no apto hoy para la tarea: {aptitud['motivo_visible']}.", "aptitud")
    elif aptitud["apto_para_tarea"] == "apto_con_observaciones":
        elevar("ambar", f"Trabajador apto con observaciones: {aptitud['motivo_visible']}.", "aptitud")

    if incidentes is None:
        porque.append("Historial de incidentes no disponible: revisarlo manualmente.")
    elif (
        incidentes["casos_similares"] >= UMBRAL_CASOS_SIMILARES
        and incidentes["riesgo_potencial_max"] in POTENCIALES_GRAVES
    ):
        elevar(
            "ambar",
            f"{incidentes['casos_similares']} incidentes similares con potencial "
            f"{incidentes['riesgo_potencial_max']}: {incidentes['patron']}",
            "incidentes",
        )

    if nivel == "rojo":
        alternativas = []
        if "aptitud" in causas_rojo:
            alternativas.append("Reasignar la tarea a otro trabajador apto del mismo turno.")
        if "area" in causas_rojo:
            alternativas.append("Esperar: no ingresar a la labor hasta corregir las condiciones y repetir la medición.")
        alternativa = " ".join(alternativas)
    elif nivel == "ambar":
        alternativa = "Si los controles no pueden aplicarse antes del inicio, reprogramar la tarea o reasignarla."
    else:
        alternativa = "No requiere alternativa."

    return {
        "nivel": nivel,
        "decision": DECISION[nivel],
        "porque": porque or ["Sin desviaciones frente a límites de la labor, aptitud ni historial de incidentes."],
        "alternativa": alternativa,
    }


def armar_checklist(senales: dict, controles: list[dict]) -> list[dict]:
    """Base: disparador `siempre` o que solo depende de `tipo_tarea`. Extra: el resto, si se cumple."""
    base, extra, vistos = [], [], set()
    for control in controles:
        if control["control"] in vistos:
            continue
        disparador = parsear_disparador(control["disparador"])
        if disparador is not None and not cumple(senales, *disparador):
            continue
        es_base = disparador is None or disparador[0] == "tipo_tarea"
        vistos.add(control["control"])
        item = ItemChecklist(
            id=control["id"],
            control=control["control"],
            riesgo_critico=control["riesgo_critico"],
            trabajo_alto_riesgo=control["trabajo_alto_riesgo"] == "si",
            jerarquia=control["jerarquia"],
            base_legal=control["base_legal"],
            origen="base" if es_base else "extra",
        )
        (base if es_base else extra).append(item.model_dump())
    return base + extra


def construir_propuesta(evaluacion: dict, checklist: list[dict]) -> PropuestaSupervisor:
    return PropuestaSupervisor(
        decision=evaluacion["decision"],
        nivel=evaluacion["nivel"],
        requiere_supervisor=any(i["trabajo_alto_riesgo"] for i in checklist),
        porque=evaluacion["porque"],
        controles_extra=[i["control"] for i in checklist if i["origen"] == "extra"],
        alternativa=evaluacion["alternativa"],
    )


def validar_firma(firma: FirmaSupervisor) -> str | None:
    if firma.accion == "ajustar" and not firma.controles_finales:
        return "Al ajustar debes indicar los controles finales."
    return None
