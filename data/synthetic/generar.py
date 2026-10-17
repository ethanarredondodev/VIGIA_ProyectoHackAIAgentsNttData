"""Generador determinista de datos sinteticos para Vigía.

Escribe en data/synthetic/:
- trabajadores.json         padron de la BD `operacion` (identidad y estado, sin datos clinicos)
- historial_trabajos.json   trabajos previos a Vigia por trabajador (BD `operacion`, sin datos clinicos)
- gemelos_clinicos.json     gemelo de cada trabajador (identidad, avatar, fatiga y datos clinicos
                            ficticios). SOLO lo carga el servicio vigia-gemelo.
- labores.json              ficha geotecnica y condiciones actuales de cada labor (agente de area)
- solicitudes.json          solicitudes de demo para la UI y `make demo`
- incidentes_etiquetados.json  incidentes con columnas estructuradas (como si los etiquetara Claude)
- incidentes_raw.csv        los mismos incidentes en texto libre, para probar scripts/etiquetar_incidentes.py

clima.json y trabajos.json NO los escribe este script: son copia de las hojas CLIMA y TRABAJO de
base_datos_mineria.xlsx (datos ficticios del equipo).

Uso: python data/synthetic/generar.py [--extra-trabajadores 20] [--extra-labores 8]
"""

import argparse
import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

DIRECTORIO = Path(__file__).parent
UNIDADES_CSV = DIRECTORIO.parent / "sheets" / "unidades_mineras.csv"
sys.path.insert(0, str(DIRECTORIO.parents[1]))

from agents.gemelo.energia import calcular_energia, total_rotacion  # noqa: E402

CONTRATISTAS = ["Contratista Minera Sintética S.A.C.", "Servicios de Perforación Andes Sintético S.A.C."]
COLOR_CASCO = {"titular": "#FFFFFF", "contratista": "#F57C00"}

# Campos de HISTORIAL_SALUD que todo gemelo lleva (cifrados); cada gemelo puede sobrescribirlos.
SALUD_BASE = {"alergias": "Ninguna conocida", "medicacion_habitual": "Ninguna", "controles_vencidos": 0}

DICTAMEN_PENDIENTE = "Pendiente de dictamen del médico ocupacional"

# Fechas del padron tomadas de base_datos_mineria.xlsx; el resto se genera con su propio azar.
FECHAS_PADRON = {"T-011": {"fecha_nacimiento": "1981-08-15", "fecha_ingreso": "2020-07-27"}}

# Gemelos de los casos de demo. T-001-D3 es Juan en el dia 3 de su rotacion (caso verde).
# Los datos clinicos son ficticios y existen para demostrar que vigia-gemelo NUNCA los expone.
GEMELOS_DEMO = [
    {"trabajador_id": "T-001", "nombre": "Juan Mamani", "cargo": "Perforista", "empleador": "contratista",
     "empresa": CONTRATISTAS[1], "seed": "juan-mamani", "color_casco": "#F57C00",
     "sueno_h": 5.1, "dia_rotacion": 12, "regimen_turno": "14x7", "exposicion_silice": "alta",
     "historial_energia": [90, 88, 84, 81, 78, 74, 70, 66, 61, 56, 50, 45, 40, 35],
     "datos_clinicos": {"diagnosticos": ["Hipoacusia neurosensorial leve bilateral"],
                        "restricciones": [], "emo_vigente_hasta": "2027-02-15"}},
    {"trabajador_id": "T-001-D3", "nombre": "Juan Mamani", "cargo": "Perforista", "empleador": "contratista",
     "empresa": CONTRATISTAS[1], "seed": "juan-mamani", "color_casco": "#F57C00",
     "sueno_h": 7.5, "dia_rotacion": 3, "regimen_turno": "14x7", "exposicion_silice": "media",
     "historial_energia": [72, 78, 84, 88, 90, 91, 89, 92, 90, 91, 92, 90, 88, 85],
     "datos_clinicos": {"diagnosticos": ["Hipoacusia neurosensorial leve bilateral"],
                        "restricciones": [], "emo_vigente_hasta": "2027-02-15"}},
    {"trabajador_id": "T-002", "nombre": "María Condori", "cargo": "Operadora de pala", "empleador": "titular",
     "empresa": "Cobre del Sur Sintetico S.A.", "seed": "maria-condori", "color_casco": "#FFFFFF",
     "sueno_h": 7.4, "dia_rotacion": 4, "regimen_turno": "14x7", "exposicion_silice": "baja",
     "datos_clinicos": {"diagnosticos": [], "restricciones": [], "emo_vigente_hasta": "2027-05-30"}},
    {"trabajador_id": "T-003", "nombre": "Pedro Huamán", "cargo": "Desatador", "empleador": "contratista",
     "empresa": CONTRATISTAS[0], "seed": "pedro-huaman", "color_casco": "#F57C00",
     "sueno_h": 3.8, "dia_rotacion": 9, "regimen_turno": "14x7", "exposicion_silice": "media",
     "datos_clinicos": {"diagnosticos": ["Lumbalgia mecánica"],
                        "restricciones": ["Evitar cargas > 25 kg"], "emo_vigente_hasta": "2026-12-20"}},
    # Raul Ticona Apaza: trabajador 11 de base_datos_mineria.xlsx (HISTORIAL_SALUD 18-23), operador de scooptram.
    # El dictamen del medico ocupacional esta pendiente; `tareas_restringidas` traduce sus hallazgos a TIPOS_TAREA
    # con criterio tecnico (F-15) y es lo unico que evaluan las reglas. Lleva historial explicito para no
    # consumir el azar y no alterar a los trabajadores generados.
    {"trabajador_id": "T-011", "nombre": "Raúl Ticona Apaza", "cargo": "Operador de scooptram",
     "empleador": "titular", "empresa": "Minera Andina Sintetica S.A.", "seed": "raul-ticona",
     "color_casco": "#FFFFFF", "sueno_h": 5.5, "dia_rotacion": 6, "regimen_turno": "14x7",
     "exposicion_silice": "alta",
     "historial_energia": [62, 60, 61, 57, 55, 56, 52, 50, 51, 47, 45, 44, 42, 40],
     "datos_clinicos": {
         "diagnosticos": [
             "Asma bronquial persistente moderada (2019), parcialmente controlada",
             "Lumbalgia crónica mecánica",
             "Secuela de esguince de tobillo izquierdo (2024): inestabilidad ocasional en terreno irregular",
             "Hallazgo sugerente de neumoconiosis incipiente (lectura OIT pendiente)",
         ],
         "restricciones": [DICTAMEN_PENDIENTE],
         "tareas_restringidas": [
             "perforacion", "voladura", "desatado", "sostenimiento", "carguio", "acarreo",
             "trabajo_en_altura", "espacio_confinado", "trabajo_en_caliente",
         ],
         "emo_vigente_hasta": "2027-04-28",
         "alergias": "Ácaros del polvo doméstico",
         "medicacion_habitual": "Corticoide inhalado + broncodilatador de acción prolongada; salbutamol de rescate",
         "controles_vencidos": 0,
         "descansos_medicos": [{"incidente_id": "INC-0022", "dias": 45}, {"incidente_id": "INC-0023", "dias": 3}],
         "evaluaciones": [
             {"salud_id": 18, "fecha": "2026-04-28", "tipo": "Examen ocupacional anual",
              "restricciones": DICTAMEN_PENDIENTE,
              "resultado": "Alterado: saturación 94 % en reposo; sibilancias leves",
              "observaciones": "Asma bronquial persistente moderada (diagnosticada en 2019), parcialmente "
                               "controlada: tos, sibilancias y falta de aire, con síntomas diurnos varias veces por "
                               "semana y despertares nocturnos ocasionales; la falta de aire aparece al caminar en "
                               "subida. Desencadenantes: polvo, humo, aire frío y esfuerzo intenso. Lumbalgia crónica "
                               "mecánica: dolor al permanecer sentado más de 2 horas y con vibración. Antecedente de "
                               "esguince de tobillo izquierdo (2024) con inestabilidad ocasional en terreno irregular."},
             {"salud_id": 19, "fecha": "2026-04-28", "tipo": "Espirometría", "restricciones": DICTAMEN_PENDIENTE,
              "resultado": "Alterado: VEF1/CVF 0,68; VEF1 71 % del predicho",
              "observaciones": "Mejora de 14 % tras broncodilatador (obstrucción parcialmente reversible)."},
             {"salud_id": 20, "fecha": "2026-04-28", "tipo": "Radiografía de tórax",
              "restricciones": DICTAMEN_PENDIENTE,
              "resultado": "Pendiente: opacidades micronodulares en campos superiores",
              "observaciones": "Hallazgo sugerente de neumoconiosis incipiente, con exposición prolongada a polvo "
                               "de mina. Lectura OIT pendiente por neumólogo ocupacional."},
             {"salud_id": 21, "fecha": "2026-04-28", "tipo": "Audiometría", "restricciones": "Ninguna",
              "resultado": "Normal", "observaciones": "Dentro de límites normales."},
             {"salud_id": 22, "fecha": "2026-08-20", "tipo": "Control de lumbalgia",
              "restricciones": DICTAMEN_PENDIENTE, "resultado": "Activa",
              "observaciones": "En fisioterapia con analgésico a demanda; sin irradiación a las piernas ni déficit "
                               "neurológico. Próximo control el 20/11/2026."},
             {"salud_id": 23, "fecha": "2026-09-05", "tipo": "Espirometría de control",
              "restricciones": DICTAMEN_PENDIENTE, "resultado": "Alterado: VEF1 68 % del predicho",
              "observaciones": "Mejora de 12 % tras broncodilatador. Control posterior a la crisis respiratoria del "
                               "02/09/2026. Próximo control el 30/10/2026."},
         ],
         # Lo que el supervisor anoto en el historial de trabajos y es dato de salud: vive aqui, no en `operacion`.
         "observaciones_de_campo": [
             {"fecha": "2024-03-18", "texto": "Caída en la rampa; esguince de tobillo izquierdo grado II tratado "
                                              "con inmovilización y fisioterapia; alta el 02/05/2024 (45 días de "
                                              "descanso)."},
             {"fecha": "2026-08-24", "texto": "El operador refirió falta de aire al caminar en subida durante el "
                                              "turno."},
             {"fecha": "2026-09-02", "texto": "Crisis con falta de aire durante la labor; atendido en el tópico con "
                                              "broncodilatador y retirado de la tarea (3 días de descanso, en "
                                              "seguimiento médico)."},
         ],
     }},
]

LABORES_DEMO = [
    {"labor": "NV-3820 TJ-12", "unidad": "UM Cerro Vigia", "co_ppm": 12, "o2_pct": 20.1,
     "ventilacion": "operativa", "ruido_dBA": 91, "ultimo_desatado_h": 26},
    {"labor": "NV-3820 GA-07", "unidad": "UM Cerro Vigia", "co_ppm": 4, "o2_pct": 20.7,
     "ventilacion": "operativa", "ruido_dBA": 82, "ultimo_desatado_h": 2},
    {"labor": "NV-3700 CH-02", "unidad": "UM Cerro Vigia", "co_ppm": 18, "o2_pct": 18.2,
     "ventilacion": "inoperativa", "ruido_dBA": 88, "ultimo_desatado_h": 8},
    {"labor": "TA-FASE4 BC-3400", "unidad": "UM Pampa Roja", "co_ppm": 3, "o2_pct": 20.9,
     "ventilacion": "natural", "ruido_dBA": 80, "ultimo_desatado_h": 6},
    {"labor": "NV-3900 GA-05", "unidad": "UM Cerro Vigia", "co_ppm": 6, "o2_pct": 20.6,
     "ventilacion": "operativa", "ruido_dBA": 84, "ultimo_desatado_h": 4},
]

# Los tres primeros son los que corre `make demo`.
SOLICITUDES_DEMO = [
    {"caso": "Juan - perforación de frente (ámbar)", "nivel_esperado": "ambar",
     "solicitud": {"tarea": "perforación de frente", "labor": "NV-3820 TJ-12", "turno": "noche",
                   "trabajador_id": "T-001", "altitud_msnm": 4210, "tipo_mineria": "subterranea",
                   "empleador": "contratista"}},
    {"caso": "Juan descansado - perforación en galería (verde)", "nivel_esperado": "verde",
     "solicitud": {"tarea": "perforación en galería", "labor": "NV-3820 GA-07", "turno": "dia",
                   "trabajador_id": "T-001-D3", "altitud_msnm": 4210, "tipo_mineria": "subterranea",
                   "empleador": "contratista"}},
    {"caso": "Juan - chimenea sin ventilación (rojo, bloqueada)", "nivel_esperado": "rojo",
     "solicitud": {"tarea": "perforación de chimenea", "labor": "NV-3700 CH-02", "turno": "noche",
                   "trabajador_id": "T-001-D3", "altitud_msnm": 4210, "tipo_mineria": "subterranea",
                   "empleador": "contratista"}},
    {"caso": "María - carguío en tajo (verde)", "nivel_esperado": "verde",
     "solicitud": {"tarea": "carguío de mineral con pala", "labor": "TA-FASE4 BC-3400", "turno": "dia",
                   "trabajador_id": "T-002", "altitud_msnm": 3400, "tipo_mineria": "tajo_abierto",
                   "empleador": "titular"}},
    {"caso": "Pedro - desatado (rojo por aptitud)", "nivel_esperado": "rojo",
     "solicitud": {"tarea": "desatado de rocas", "labor": "NV-3900 GA-05", "turno": "noche",
                   "trabajador_id": "T-003", "altitud_msnm": 4210, "tipo_mineria": "subterranea",
                   "empleador": "contratista"}},
    {"caso": "Raúl - acarreo con scooptram (rojo por restricción médica)", "nivel_esperado": "rojo",
     "solicitud": {"tarea": "acarreo de mineral con scooptram", "labor": "NV-3820 GA-07", "turno": "dia",
                   "trabajador_id": "T-011", "altitud_msnm": 3800, "tipo_mineria": "subterranea",
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

# Incidentes de base_datos_mineria.xlsx ligados a un trabajador (HISTORIAL_INCIDENTES 2 y 8 de Raul).
# tipo_tarea `carguio` es como clasifica Vigia una tarea con scooptram. El resumen describe el evento; los
# sintomas, el tratamiento y los dias de descanso van cifrados al gemelo.
# "Emergencia médica (crisis respiratoria)" y "En seguimiento médico" de la planilla quedan sin el detalle clinico.
# (id, fecha, trabajador_id, tipo_tarea, labor_tipo, turno, riesgo_critico, potencial, resumen_es, causa_probable,
#  tipo_incidente, gravedad, estado)
INCIDENTES_DE_TRABAJADORES = [
    ("INC-0022", "2024-03-18", "T-011", "carguio", "rampa", "dia", "otro", "medio",
     "Caída en una rampa de la mina durante el acarreo con scooptram; esguince de tobillo.",
     "Sin causa registrada en el reporte.", "Caída con lesión (esguince)", "moderada", "cerrado"),
    ("INC-0023", "2026-09-02", "T-011", "carguio", "galeria", "dia", "silice", "alto",
     "Emergencia médica durante el acarreo con scooptram en la galería; atendido en el tópico y retirado de la tarea.",
     "Sin causa registrada en el reporte.", "Emergencia médica", "moderada", "en_seguimiento"),
]

# HISTORIAL_TRABAJOS 21-23 de base_datos_mineria.xlsx: trabajos de Raul antes de Vigia. ZM-003 (nivel 3,
# galeria de perforacion) corresponde a la labor NV-3820 GA-07. Las observaciones con datos de salud quedaron
# en el gemelo; aqui solo el hecho operativo.
HISTORIAL_TRABAJOS = [
    {"historial_trabajo_id": "HT-0021", "trabajador_id": "T-011", "labor": "NV-3820 GA-07",
     "trabajo_id": 11, "descripcion_realizada": "Acarreo subterráneo con scooptram.", "incidente_id": "INC-0022",
     "fecha_inicio": "2024-03-18", "fecha_fin": "2024-03-18", "turno": "dia", "estado_trabajo": "interrumpido",
     "observaciones": "Caída en la rampa; tarea interrumpida.",
     "validado_por": "Ing. Héctor Medina Salas", "fecha_validacion": "2024-03-19",
     "costo_real": 600.00, "duracion_real": 3.00},
    {"historial_trabajo_id": "HT-0022", "trabajador_id": "T-011", "labor": "NV-3820 GA-07",
     "trabajo_id": 11, "descripcion_realizada": "Acarreo subterráneo con scooptram.", "incidente_id": None,
     "fecha_inicio": "2026-08-24", "fecha_fin": "2026-08-24", "turno": "dia", "estado_trabajo": "completado",
     "observaciones": "Completado; el operador reportó una molestia de salud, derivada a salud ocupacional.",
     "validado_por": "Ing. Héctor Medina Salas", "fecha_validacion": "2026-08-25",
     "costo_real": 2950.00, "duracion_real": 12.00},
    {"historial_trabajo_id": "HT-0023", "trabajador_id": "T-011", "labor": "NV-3820 GA-07",
     "trabajo_id": 11, "descripcion_realizada": "Acarreo subterráneo con scooptram.", "incidente_id": "INC-0023",
     "fecha_inicio": "2026-09-02", "fecha_fin": "2026-09-02", "turno": "dia", "estado_trabajo": "interrumpido",
     "observaciones": "Emergencia médica durante la labor; atendido en el tópico y retirado de la tarea.",
     "validado_por": "Ing. Patricia Rojas Valdivia", "fecha_validacion": "2026-09-03",
     "costo_real": 1000.00, "duracion_real": 4.00},
]

# Ficha geotecnica de ZONA_MINERA por tipo de mineria, tomada de base_datos_mineria.xlsx (ZM-003 subterranea,
# ZM-001 tajo). La altitud va al final de peligros_conocidos, como en la planilla.
GEOTECNIA = {
    "subterranea": {
        "tipo": "Mina subterránea", "tipo_suelo": "Roca granodiorítica competente con zonas de falla",
        "angulo_talud": None, "riesgo_geotecnico": "medio",
        "peligros_conocidos": "Polvo de sílice, ruido muy alto, caída de rocas del techo, ventilación limitada, "
                              "gases de voladura, rampa con pendiente",
        "tareas_restringidas": "Ingreso sin sostenimiento verificado; permanencia en el frente antes de cumplir el "
                               "tiempo de ventilación tras una voladura.",
        "controles_requeridos": "Ventilación forzada, sostenimiento con pernos, monitoreo de gases, riego para el "
                                "polvo, respirador, autorrescatador.",
    },
    "tajo_abierto": {
        "tipo": "Tajo abierto", "tipo_suelo": "Roca andesítica fracturada con relleno de grava",
        "angulo_talud": 38.00, "riesgo_geotecnico": "medio",
        "peligros_conocidos": "Rampa con pendiente de 8 a 10 %; neblina y polvo reducen la visibilidad; pérdida de "
                              "tracción con lluvia, granizo o hielo; frío y viento",
        "tareas_restringidas": "Tránsito de vehículos livianos y peatones con lluvia, granizo o hielo en la rampa.",
        "controles_requeridos": "Bermas de seguridad, riego de la rampa, señalización, límite de velocidad, suspensión "
                                "del tránsito con visibilidad mínima.",
    },
}
NOMBRE_LABOR = {"TJ": "tajeo", "GA": "galería", "CH": "chimenea", "RP": "rampa", "XC": "crucero", "BC": "banco"}
# NV-3820 GA-07 es ZM-003 de la planilla: conserva su nombre, altitud e inspeccion.
LABORES_DE_LA_PLANILLA = {
    "NV-3820 GA-07": {"nombre": "Nivel 3, galería de perforación (3,800 msnm)", "altitud": 3800,
                      "ultima_inspeccion": "2026-09-28"},
}

NOMBRES = ["Carlos", "Rosa", "Edwin", "Yeni", "Wilber", "Nely", "Hugo", "Elsa", "Percy", "Gladys",
           "Fredy", "Delia", "Rolando", "Marisol", "Teodoro", "Celia", "Abel", "Lucía", "Rubén", "Flor"]
APELLIDOS = ["Quispe", "Huanca", "Choque", "Apaza", "Flores", "Torres", "Ramos", "Vilca", "Poma", "Yupanqui"]
CARGOS = ["Perforista", "Ayudante de perforación", "Operador de scoop", "Desatador", "Bodeguero de explosivos",
          "Mecánico", "Electricista", "Operador de shotcrete"]
TAREAS = ["perforación de frente", "desatado de rocas", "limpieza con scoop", "sostenimiento con pernos",
          "mantenimiento de bombas", "carguío de taladros"]


def leer_unidades() -> dict[str, dict]:
    with UNIDADES_CSV.open(encoding="utf-8") as f:
        return {fila["unidad"]: fila for fila in csv.DictReader(f)}


def historial_hacia(energia: int, azar: random.Random) -> list[int]:
    """14 dias de energia que terminan en el valor actual (paseo aleatorio hacia atras)."""
    valores = [energia]
    for _ in range(13):
        valores.append(max(10, min(95, valores[-1] + azar.randint(-6, 9))))
    return list(reversed(valores))


def completar_avatar(gemelo: dict, azar: random.Random) -> dict:
    energia = calcular_energia(gemelo["sueno_h"], gemelo["dia_rotacion"], total_rotacion(gemelo["regimen_turno"]))
    historial = gemelo.get("historial_energia") or historial_hacia(energia, azar)
    if historial[-1] != energia:
        raise ValueError(f"{gemelo['trabajador_id']}: el historial debe terminar en la energia actual {energia}")
    return {**gemelo, "historial_energia": historial}


def padron(gemelo: dict) -> dict:
    """El azar sale del seed del avatar: no altera el resto y T-001-D3 (Juan otro dia) recibe las fechas de Juan."""
    nombres, apellidos = gemelo["nombre"].split(" ", 1)
    azar = random.Random(gemelo["seed"])
    nacimiento = date(azar.randint(1975, 2000), azar.randint(1, 12), azar.randint(1, 28))
    ingreso = date(min(2025, nacimiento.year + azar.randint(20, 30)), azar.randint(1, 12), azar.randint(1, 28))
    fechas = FECHAS_PADRON.get(gemelo["trabajador_id"]) or {
        "fecha_nacimiento": nacimiento.isoformat(), "fecha_ingreso": ingreso.isoformat(),
    }
    return {
        "trabajador_id": gemelo["trabajador_id"], "nombres": nombres, "apellidos": apellidos,
        "cargo": gemelo["cargo"], "empresa": gemelo["empresa"], "empleador": gemelo["empleador"],
        **fechas, "estado": "activo",
    }


def ficha_labor(labor: dict, mineria: str, n: int) -> dict:
    """ZONA_MINERA de la labor: geotecnia segun el tipo de mineria; nombre y altitud salen del codigo (NV-3820 GA-07)."""
    nivel, codigo = labor["labor"].split(" ")
    prefijo, numero = codigo.split("-")
    if mineria == "subterranea":
        altitud, lugar = int(nivel.removeprefix("NV-")), f"Nivel {nivel.removeprefix('NV-')}"
    else:
        altitud, lugar = int(numero), f"Tajo {nivel.removeprefix('TA-').lower().replace('fase', 'fase ')}"
    geotecnia = GEOTECNIA[mineria]
    ficha = {
        "nombre": f"{lugar}, {NOMBRE_LABOR[prefijo]} {numero} ({altitud:,} msnm)", "altitud": altitud,
        "ultima_inspeccion": (date(2026, 9, 1) + timedelta(days=2 * n)).isoformat(),
        **LABORES_DE_LA_PLANILLA.get(labor["labor"], {}),
    }
    return {
        "nombre": ficha["nombre"], "tipo": geotecnia["tipo"], "tipo_suelo": geotecnia["tipo_suelo"],
        "angulo_talud": geotecnia["angulo_talud"],
        "riesgo_geotecnico": "alto" if prefijo == "CH" else geotecnia["riesgo_geotecnico"],
        "peligros_conocidos": f"{geotecnia['peligros_conocidos']}; altitud de {ficha['altitud']:,} msnm.",
        "tareas_restringidas": geotecnia["tareas_restringidas"],
        "controles_requeridos": geotecnia["controles_requeridos"],
        "ultima_inspeccion": ficha["ultima_inspeccion"],
    }


def generar(extra_trabajadores: int, extra_labores: int) -> dict:
    azar = random.Random(42)
    unidades = leer_unidades()
    subterraneas = [u for u, d in unidades.items() if d["tipo_mineria"] == "subterranea"]

    gemelos = [completar_avatar(g, azar) for g in GEMELOS_DEMO]
    for i in range(extra_trabajadores):
        unidad = azar.choice(subterraneas)
        empleador = azar.choice(["titular", "contratista"])
        nombre = f"{NOMBRES[i % len(NOMBRES)]} {azar.choice(APELLIDOS)}"
        gemelos.append(completar_avatar({
            "trabajador_id": f"T-{i + 101:03d}",
            "nombre": nombre,
            "cargo": azar.choice(CARGOS),
            "empleador": empleador,
            "empresa": unidades[unidad]["empresa"] if empleador == "titular" else azar.choice(CONTRATISTAS),
            "seed": nombre.lower().replace(" ", "-"),
            "color_casco": COLOR_CASCO[empleador],
            "sueno_h": round(azar.uniform(4.5, 8.5), 1),
            "dia_rotacion": azar.randint(1, total_rotacion(unidades[unidad]["regimen_turno"])),
            "regimen_turno": unidades[unidad]["regimen_turno"],
            "exposicion_silice": azar.choice(["baja", "media", "alta"]),
            "datos_clinicos": {"diagnosticos": [], "restricciones": [], "emo_vigente_hasta": "2027-06-30"},
        }, azar))
    gemelos = [{**g, "datos_clinicos": {**SALUD_BASE, **g["datos_clinicos"]}} for g in gemelos]

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
    labores = [{**lab, **ficha_labor(lab, unidades[lab["unidad"]]["tipo_mineria"], n)} for n, lab in enumerate(labores)]

    solicitudes = list(SOLICITUDES_DEMO)
    for gemelo in gemelos[len(GEMELOS_DEMO):][:6]:
        unidad = next(u for u, d in unidades.items() if d["regimen_turno"] == gemelo["regimen_turno"]
                      and d["tipo_mineria"] == "subterranea")
        labor = azar.choice([lab for lab in labores if lab["unidad"] == unidad] or labores)
        solicitudes.append({
            "caso": f"{gemelo['nombre']} - aleatorio",
            "nivel_esperado": None,
            "solicitud": {
                "tarea": azar.choice(TAREAS),
                "labor": labor["labor"],
                "turno": azar.choice(["dia", "noche"]),
                "trabajador_id": gemelo["trabajador_id"],
                "altitud_msnm": int(unidades[unidad]["altitud_msnm"]),
                "tipo_mineria": "subterranea",
                "empleador": gemelo["empleador"],
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
            "trabajador_id": None,
            "tipo_incidente": None,
            "gravedad": None,
            "estado": "cerrado",
        })
    for (id_, fecha, trabajador, tarea, labor, turno, riesgo, potencial, resumen, causa,
         tipo_incidente, gravedad, estado) in INCIDENTES_DE_TRABAJADORES:
        incidentes.append({
            "id": id_, "fecha": fecha, "unidad": "UM Cerro Vigia", "tipo_mineria": "subterranea",
            "tipo_tarea": tarea, "labor_tipo": labor, "turno": turno, "riesgo_critico": riesgo,
            "causa_probable": causa, "potencial": potencial, "resumen_es": resumen, "origen": "sintetico",
            "trabajador_id": trabajador, "tipo_incidente": tipo_incidente, "gravedad": gravedad, "estado": estado,
        })

    return {
        "trabajadores": [padron(g) for g in gemelos],
        "historial_trabajos": HISTORIAL_TRABAJOS,
        "gemelos_clinicos": gemelos,
        "labores": labores,
        "solicitudes": solicitudes,
        "incidentes_etiquetados": incidentes,
    }


def escribir(datos: dict) -> None:
    for nombre, contenido in datos.items():
        ruta = DIRECTORIO / f"{nombre}.json"
        ruta.write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(ruta.relative_to(DIRECTORIO.parents[1]).as_posix())
    ruta_raw = DIRECTORIO / "incidentes_raw.csv"
    with ruta_raw.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["id", "fecha", "unidad", "descripcion"])
        for inc in datos["incidentes_etiquetados"]:
            turno = "noche" if inc["turno"] == "noche" else "día"
            escritor.writerow([inc["id"], inc["fecha"], inc["unidad"],
                               f"Turno {turno}. {inc['resumen_es']} Causa identificada: {inc['causa_probable']}"])
    print(ruta_raw.relative_to(DIRECTORIO.parents[1]).as_posix())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extra-trabajadores", type=int, default=20)
    parser.add_argument("--extra-labores", type=int, default=8)
    args = parser.parse_args()
    escribir(generar(args.extra_trabajadores, args.extra_labores))
