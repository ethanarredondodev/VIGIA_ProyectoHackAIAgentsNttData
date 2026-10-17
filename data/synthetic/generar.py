"""Generador determinista de datos sinteticos para Vigia.

Escribe en data/synthetic/:
- trabajadores.json         padron publico (id, nombre, puesto, empleador, unidad)
- gemelos_clinicos.json     datos de la zona clinica: SOLO los carga el servicio gemelo
- labores.json              condiciones actuales de cada labor (agente de area)
- solicitudes.json          solicitudes de demo para la UI y `make demo`
- incidentes_etiquetados.json  incidentes con columnas estructuradas (como si los etiquetara Claude)
- incidentes_raw.csv        los mismos incidentes en texto libre, para probar scripts/etiquetar_incidentes.py

Uso: python data/synthetic/generar.py [--extra-trabajadores 16] [--extra-labores 8]
"""

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

DIRECTORIO = Path(__file__).parent
UNIDADES_CSV = DIRECTORIO.parent / "sheets" / "unidades_mineras.csv"

TRABAJADORES_DEMO = [
    {"trabajador_id": "T-001", "nombre": "Juan Mamani", "puesto": "perforista",
     "empleador": "contratista", "unidad": "UM Cerro Vigia"},
    {"trabajador_id": "T-002", "nombre": "María Condori", "puesto": "operadora de pala",
     "empleador": "titular", "unidad": "UM Pampa Roja"},
    {"trabajador_id": "T-003", "nombre": "Pedro Huamán", "puesto": "desatador",
     "empleador": "contratista", "unidad": "UM Cerro Vigia"},
    {"trabajador_id": "T-004", "nombre": "Luis Ccahuana", "puesto": "operador de shotcrete",
     "empleador": "titular", "unidad": "UM Cerro Vigia"},
]

# Datos clinicos ficticios. Existen para demostrar que el gemelo NUNCA los expone.
GEMELOS_DEMO = {
    "T-001": {"sueno_h": 5.1, "dia_rotacion": 12, "regimen_turno": "14x7", "exposicion_silice": "alta",
              "datos_clinicos": {"diagnosticos": ["Hipoacusia neurosensorial leve bilateral"],
                                 "restricciones": [], "emo_vigente_hasta": "2027-02-15"}},
    "T-002": {"sueno_h": 7.4, "dia_rotacion": 4, "regimen_turno": "14x7", "exposicion_silice": "baja",
              "datos_clinicos": {"diagnosticos": [], "restricciones": [], "emo_vigente_hasta": "2027-05-30"}},
    "T-003": {"sueno_h": 3.8, "dia_rotacion": 9, "regimen_turno": "14x7", "exposicion_silice": "media",
              "datos_clinicos": {"diagnosticos": ["Lumbalgia mecánica"],
                                 "restricciones": ["Evitar cargas > 25 kg"], "emo_vigente_hasta": "2026-12-20"}},
    "T-004": {"sueno_h": 7.0, "dia_rotacion": 6, "regimen_turno": "14x7", "exposicion_silice": "media",
              "datos_clinicos": {"diagnosticos": [], "restricciones": [], "emo_vigente_hasta": "2027-01-10"}},
}

LABORES_DEMO = [
    {"labor": "NV-3820 TJ-12", "unidad": "UM Cerro Vigia", "co_ppm": 12, "o2_pct": 20.1,
     "ventilacion": "operativa", "ruido_dBA": 91, "ultimo_desatado_h": 26},
    {"labor": "TA-FASE4 BC-3400", "unidad": "UM Pampa Roja", "co_ppm": 3, "o2_pct": 20.9,
     "ventilacion": "natural", "ruido_dBA": 80, "ultimo_desatado_h": 6},
    {"labor": "NV-3900 GA-05", "unidad": "UM Cerro Vigia", "co_ppm": 6, "o2_pct": 20.6,
     "ventilacion": "operativa", "ruido_dBA": 84, "ultimo_desatado_h": 4},
    {"labor": "NV-3700 CH-02", "unidad": "UM Cerro Vigia", "co_ppm": 18, "o2_pct": 19.2,
     "ventilacion": "deficiente", "ruido_dBA": 88, "ultimo_desatado_h": 8},
]

SOLICITUDES_DEMO = [
    {"caso": "Juan - perforacion de frente (ambar)", "nombre": "Juan Mamani",
     "solicitud": {"tarea": "perforación de frente", "labor": "NV-3820 TJ-12", "turno": "noche",
                   "trabajador_id": "T-001", "altitud_msnm": 4210, "tipo_mineria": "subterranea",
                   "empleador": "contratista"}},
    {"caso": "María - carguío en tajo (verde)", "nombre": "María Condori",
     "solicitud": {"tarea": "carguío de mineral con pala", "labor": "TA-FASE4 BC-3400", "turno": "dia",
                   "trabajador_id": "T-002", "altitud_msnm": 3400, "tipo_mineria": "tajo_abierto",
                   "empleador": "titular"}},
    {"caso": "Pedro - desatado (rojo por aptitud)", "nombre": "Pedro Huamán",
     "solicitud": {"tarea": "desatado de rocas", "labor": "NV-3900 GA-05", "turno": "noche",
                   "trabajador_id": "T-003", "altitud_msnm": 4210, "tipo_mineria": "subterranea",
                   "empleador": "contratista"}},
    {"caso": "Luis - shotcrete en chimenea (rojo por atmósfera)", "nombre": "Luis Ccahuana",
     "solicitud": {"tarea": "sostenimiento con shotcrete", "labor": "NV-3700 CH-02", "turno": "dia",
                   "trabajador_id": "T-004", "altitud_msnm": 4210, "tipo_mineria": "subterranea",
                   "empleador": "titular"}},
]

# (id, tipo_mineria, tipo_tarea, labor_tipo, turno, riesgo_critico, potencial, resumen_es, causa_probable)
# Exactamente 3 casos coinciden con el caso de Juan (subterranea, perforacion, frente_avance, noche).
INCIDENTES = [
    ("INC-0001", "subterranea", "voladura", "frente_avance", "noche", "explosivos", "critico",
     "Detonación prematura durante el carguío de taladros del frente; dos trabajadores con trauma acústico.",
     "Fulminante dañado y circuito sin verificar antes del carguío."),
    ("INC-0002", "subterranea", "carguio", "galeria", "noche", "equipo_movil", "alto",
     "Un scoop golpeó a un ayudante que transitaba por la galería con baja visibilidad.",
     "Sin vigía ni separación entre tránsito peatonal y de equipos."),
    ("INC-0003", "subterranea", "perforacion", "frente_avance", "dia", "desprendimiento_de_roca", "medio",
     "Roca suelta cayó cerca del perforista durante la perforación del frente en turno día; sin lesiones.",
     "Desatado incompleto en la corona."),
    ("INC-0004", "subterranea", "sostenimiento", "tajeo", "dia", "desprendimiento_de_roca", "medio",
     "Durante la instalación de pernos se desprendió un bloque del hastial y golpeó el equipo.",
     "Secuencia de sostenimiento no respetada."),
    ("INC-0005", "subterranea", "desatado", "galeria", "noche", "desprendimiento_de_roca", "alto",
     "Un bloque de roca cayó sobre la barretilla del desatador y le provocó un esguince de muñeca.",
     "Barretilla de longitud inadecuada y posición debajo de la roca suelta."),
    ("INC-0006", "subterranea", "mantenimiento", "rampa", "dia", "energia_electrica", "medio",
     "Descarga eléctrica leve al manipular un tablero de bombas en la rampa.",
     "No se aplicó bloqueo y etiquetado."),
    ("INC-0007", "subterranea", "perforacion", "frente_avance", "noche", "desprendimiento_de_roca", "alto",
     "Desprendimiento de roca del techo durante la perforación del frente en turno noche; el perforista "
     "sufrió una contusión en el hombro.",
     "Desatado insuficiente después de la voladura del turno anterior."),
    ("INC-0008", "subterranea", "perforacion", "tajeo", "noche", "atmosfera_peligrosa", "alto",
     "El perforista presentó mareos por acumulación de gases después de la voladura en el tajeo.",
     "Ventilación auxiliar apagada y sin medición de gases antes del ingreso."),
    ("INC-0009", "tajo_abierto", "acarreo", "rampa", "noche", "equipo_movil", "critico",
     "Un camión de acarreo se salió de la vía en la rampa del tajo durante el turno noche.",
     "Fatiga del operador al final del turno."),
    ("INC-0010", "tajo_abierto", "carguio", "banco", "dia", "equipo_movil", "medio",
     "La pala golpeó la tolva del camión durante el carguío; el operador resultó ileso.",
     "Comunicación radial deficiente entre pala y camión."),
    ("INC-0011", "subterranea", "izaje", "chimenea", "dia", "izaje", "alto",
     "Falla del freno del winche durante el izaje de materiales en la chimenea.",
     "Mantenimiento preventivo vencido."),
    ("INC-0012", "subterranea", "perforacion", "frente_avance", "noche", "desprendimiento_de_roca", "alto",
     "Caída de un planchón desde la corona mientras se perforaba el frente de avance de noche; sin "
     "lesionados, daño a la perforadora.",
     "Sostenimiento con pernos pendiente en los últimos 2 m del frente."),
    ("INC-0013", "subterranea", "sostenimiento", "chimenea", "dia", "atmosfera_peligrosa", "alto",
     "El operador de shotcrete presentó síntomas de hipoxia en una chimenea con ventilación deficiente.",
     "Ingreso sin medición de oxígeno."),
    ("INC-0014", "subterranea", "trabajo_en_caliente", "galeria", "dia", "otro", "medio",
     "Amago de incendio por chispas de soldadura sobre material combustible en la galería.",
     "Área de trabajo en caliente sin limpieza ni extintor."),
    ("INC-0015", "subterranea", "acarreo", "rampa", "noche", "equipo_movil", "alto",
     "Un volquete y una camioneta casi colisionan en la rampa por exceso de velocidad.",
     "Incumplimiento de los límites de velocidad."),
    ("INC-0016", "subterranea", "trabajo_en_altura", "chimenea", "dia", "caida_de_altura", "alto",
     "Un trabajador resbaló en la plataforma de la chimenea; el arnés detuvo la caída.",
     "Plataforma húmeda y sin baranda."),
    ("INC-0017", "tajo_abierto", "perforacion", "banco", "dia", "silice", "medio",
     "Exposición a polvo durante la perforación en seco en el banco.",
     "Sistema de supresión de polvo inoperativo."),
    ("INC-0018", "subterranea", "desatado", "frente_avance", "noche", "desprendimiento_de_roca", "alto",
     "Desatador lesionado por un planchón en el frente de avance durante el turno noche.",
     "Iluminación insuficiente en el frente."),
    ("INC-0019", "subterranea", "perforacion", "frente_avance", "noche", "desprendimiento_de_roca", "alto",
     "Lesión en la mano por roca suelta desprendida del hastial durante la perforación nocturna del frente.",
     "Iluminación deficiente que impidió identificar roca suelta durante el desatado."),
    ("INC-0020", "subterranea", "espacio_confinado", "otro", "dia", "espacio_confinado", "alto",
     "Un trabajador ingresó a una tolva sin permiso para destrabar mineral.",
     "Ausencia de PETAR y de vigía en el ingreso."),
    ("INC-0021", "subterranea", "voladura", "tajeo", "dia", "explosivos", "alto",
     "Proyección de rocas alcanzó la zona de un vigía mal ubicado.",
     "Vigía ubicado a distancia insegura."),
]

NOMBRES = ["Carlos", "Rosa", "Edwin", "Yeni", "Wilber", "Nely", "Hugo", "Elsa", "Percy", "Gladys",
           "Fredy", "Delia", "Rolando", "Marisol", "Teodoro", "Celia"]
APELLIDOS = ["Quispe", "Huanca", "Choque", "Apaza", "Flores", "Torres", "Ramos", "Vilca", "Poma", "Yupanqui"]
PUESTOS = ["perforista", "ayudante de perforación", "operador de scoop", "desatador", "bodeguero de explosivos",
           "mecánico", "electricista", "operador de shotcrete"]
TAREAS = ["perforación de frente", "desatado de rocas", "limpieza con scoop", "sostenimiento con pernos",
          "mantenimiento de bombas", "carguío de taladros"]


def leer_unidades() -> dict[str, dict]:
    with UNIDADES_CSV.open(encoding="utf-8") as f:
        return {fila["unidad"]: fila for fila in csv.DictReader(f)}


def generar(extra_trabajadores: int, extra_labores: int) -> dict:
    azar = random.Random(42)
    unidades = leer_unidades()
    subterraneas = [u for u, d in unidades.items() if d["tipo_mineria"] == "subterranea"]

    trabajadores = list(TRABAJADORES_DEMO)
    gemelos = [{"trabajador_id": k, **v} for k, v in GEMELOS_DEMO.items()]
    for i in range(extra_trabajadores):
        unidad = azar.choice(subterraneas)
        trabajador_id = f"T-{i + 101:03d}"
        trabajadores.append({
            "trabajador_id": trabajador_id,
            "nombre": f"{NOMBRES[i % len(NOMBRES)]} {azar.choice(APELLIDOS)}",
            "puesto": azar.choice(PUESTOS),
            "empleador": azar.choice(["titular", "contratista"]),
            "unidad": unidad,
        })
        gemelos.append({
            "trabajador_id": trabajador_id,
            "sueno_h": round(azar.uniform(4.5, 8.5), 1),
            "dia_rotacion": azar.randint(1, 14),
            "regimen_turno": unidades[unidad]["regimen_turno"],
            "exposicion_silice": azar.choice(["baja", "media", "alta"]),
            "datos_clinicos": {"diagnosticos": [], "restricciones": [], "emo_vigente_hasta": "2027-06-30"},
        })

    labores = list(LABORES_DEMO)
    prefijos = ["GA", "RP", "XC", "TJ"]
    for i in range(extra_labores):
        unidad = azar.choice(subterraneas)
        nivel = int(unidades[unidad]["altitud_msnm"]) - azar.choice([0, 100, 200])
        labores.append({
            "labor": f"NV-{nivel} {prefijos[i % len(prefijos)]}-{i + 20:02d}",
            "unidad": unidad,
            "co_ppm": azar.randint(0, 20),
            "o2_pct": round(azar.uniform(19.6, 20.9), 1),
            "ventilacion": azar.choice(["operativa", "operativa", "operativa", "deficiente"]),
            "ruido_dBA": azar.randint(75, 98),
            "ultimo_desatado_h": azar.randint(1, 30),
        })

    solicitudes = list(SOLICITUDES_DEMO)
    for trabajador in trabajadores[len(TRABAJADORES_DEMO):][:6]:
        unidad = unidades[trabajador["unidad"]]
        labor = azar.choice([lab for lab in labores if lab["unidad"] == trabajador["unidad"]] or labores)
        solicitudes.append({
            "caso": f"{trabajador['nombre']} - aleatorio",
            "nombre": trabajador["nombre"],
            "solicitud": {
                "tarea": azar.choice(TAREAS),
                "labor": labor["labor"],
                "turno": azar.choice(["dia", "noche"]),
                "trabajador_id": trabajador["trabajador_id"],
                "altitud_msnm": int(unidad["altitud_msnm"]),
                "tipo_mineria": unidad["tipo_mineria"],
                "empleador": trabajador["empleador"],
            },
        })

    tajo = [u for u, d in unidades.items() if d["tipo_mineria"] == "tajo_abierto"]
    incidentes = []
    for n, (id_, mineria, tarea, labor, turno, riesgo, potencial, resumen, causa) in enumerate(INCIDENTES):
        incidentes.append({
            "id": id_,
            "fecha": (date(2024, 1, 15) + timedelta(days=37 * n)).isoformat(),
            "unidad": azar.choice(subterraneas if mineria == "subterranea" else tajo),
            "tipo_mineria": mineria,
            "tipo_tarea": tarea,
            "labor_tipo": labor,
            "turno": turno,
            "riesgo_critico": riesgo,
            "causa_probable": causa,
            "potencial": potencial,
            "resumen_es": resumen,
            "origen": "sintetico",
        })

    return {
        "trabajadores": trabajadores,
        "gemelos_clinicos": gemelos,
        "labores": labores,
        "solicitudes": solicitudes,
        "incidentes_etiquetados": incidentes,
    }


def escribir(datos: dict) -> None:
    for nombre, contenido in datos.items():
        ruta = DIRECTORIO / f"{nombre}.json"
        ruta.write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(ruta.relative_to(DIRECTORIO.parent.parent))
    ruta_raw = DIRECTORIO / "incidentes_raw.csv"
    with ruta_raw.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["id", "fecha", "unidad", "descripcion"])
        for inc in datos["incidentes_etiquetados"]:
            turno = "noche" if inc["turno"] == "noche" else "día"
            escritor.writerow([inc["id"], inc["fecha"], inc["unidad"],
                               f"Turno {turno}. {inc['resumen_es']} Causa identificada: {inc['causa_probable']}"])
    print(ruta_raw.relative_to(DIRECTORIO.parent.parent))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extra-trabajadores", type=int, default=16)
    parser.add_argument("--extra-labores", type=int, default=8)
    args = parser.parse_args()
    escribir(generar(args.extra_trabajadores, args.extra_labores))
