"""Vocabulario controlado compartido por todos los agentes.

Los valores de estas listas son los que Claude usa al etiquetar incidentes y los
que las reglas de los CSV pueden referenciar. Cambiarlos rompe el filtrado.
"""

import re
import unicodedata

TIPOS_TAREA = [
    "perforacion",
    "voladura",
    "desatado",
    "sostenimiento",
    "carguio",
    "acarreo",
    "mantenimiento",
    "izaje",
    "trabajo_en_altura",
    "espacio_confinado",
    "trabajo_en_caliente",
    "otro",
]

TIPOS_LABOR = [
    "frente_avance",
    "tajeo",
    "galeria",
    "rampa",
    "chimenea",
    "crucero",
    "banco",
    "planta",
    "otro",
]

RIESGOS_CRITICOS = [
    "desprendimiento_de_roca",
    "atmosfera_peligrosa",
    "caida_de_altura",
    "equipo_movil",
    "explosivos",
    "energia_electrica",
    "izaje",
    "espacio_confinado",
    "ruido",
    "fatiga",
    "silice",
    "otro",
]

POTENCIALES = ["bajo", "medio", "alto", "critico"]

VARIABLES_PERMITIDAS = {
    "sueno_h",
    "dia_rotacion",
    "regimen_turno",
    "altitud_msnm",
    "tipo_mineria",
    "empleador",
    "exposicion_silice",
    "co_ppm",
    "o2_pct",
    "ruido_dBA",
    "ultimo_desatado_h",
    "ventilacion",
    "turno",
    "tipo_tarea",
}

# Senales que el orquestador obtiene de otros agentes y que solo pueden usarse
# en la columna `disparador` de controles_iperc.
SENALES_DERIVADAS = {"apto_para_tarea", "casos_similares", "riesgo_potencial_max"}

_PALABRAS_TAREA = [
    ("voladura", ["voladura", "disparo", "explosivo", "carguio de taladros"]),
    ("perforacion", ["perfor", "taladr", "jumbo", "jackleg"]),
    ("desatado", ["desatado", "desatar"]),
    ("sostenimiento", ["sostenimiento", "shotcrete", "perno", "malla", "cimbra", "enmaderado"]),
    ("carguio", ["carguio", "limpieza", "scoop", "pala"]),
    ("acarreo", ["acarreo", "transporte", "volquete", "camion"]),
    ("izaje", ["izaje", "winche", "jaula"]),
    ("trabajo_en_altura", ["altura", "andamio"]),
    ("espacio_confinado", ["confinado", "tolva", "tanque"]),
    ("trabajo_en_caliente", ["soldadura", "oxicorte", "caliente"]),
    ("mantenimiento", ["mantenimiento", "reparacion"]),
]

_PREFIJOS_LABOR = {
    "TJ": "tajeo",
    "GA": "galeria",
    "GL": "galeria",
    "RP": "rampa",
    "CH": "chimenea",
    "XC": "crucero",
    "CX": "crucero",
    "BC": "banco",
    "TA": "banco",
}


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.lower().strip()


def clasificar_tarea(tarea: str) -> str:
    texto = normalizar(tarea)
    for tipo, palabras in _PALABRAS_TAREA:
        if any(p in texto for p in palabras):
            return tipo
    return "otro"


def clasificar_labor(tarea: str, labor: str) -> str:
    if "frente" in normalizar(tarea):
        return "frente_avance"
    for prefijo in re.findall(r"\b([A-Z]{2})-", labor.upper()):
        if prefijo in _PREFIJOS_LABOR:
            return _PREFIJOS_LABOR[prefijo]
    return "otro"
