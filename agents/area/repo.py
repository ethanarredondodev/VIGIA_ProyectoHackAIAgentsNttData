"""Catalogo de labores (ZONA MINERA), condiciones actuales de cada una y clima del yacimiento.
Postgres (proyecto `operacion`) o memoria si no hay DATABASE_URL."""

import json

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agents.comun.sheets import DATA_DIR

ESQUEMA = """
CREATE TABLE IF NOT EXISTS labores (
    labor TEXT PRIMARY KEY,
    unidad TEXT NOT NULL,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    tipo_suelo TEXT NOT NULL,
    angulo_talud NUMERIC(5, 2),
    riesgo_geotecnico TEXT NOT NULL CHECK (riesgo_geotecnico IN ('bajo', 'medio', 'alto')),
    peligros_conocidos TEXT,
    tareas_restringidas TEXT,
    controles_requeridos TEXT,
    ultima_inspeccion DATE NOT NULL
);
CREATE TABLE IF NOT EXISTS condiciones_labor (
    labor TEXT PRIMARY KEY REFERENCES labores (labor),
    co_ppm DOUBLE PRECISION NOT NULL,
    o2_pct DOUBLE PRECISION NOT NULL,
    ventilacion TEXT NOT NULL,
    ruido_dba DOUBLE PRECISION NOT NULL,
    ultimo_desatado_h DOUBLE PRECISION NOT NULL,
    medido_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Clima general del yacimiento por fecha, como en el diagrama: no depende de una labor.
CREATE TABLE IF NOT EXISTS clima (
    clima_id INTEGER PRIMARY KEY,
    fecha DATE NOT NULL UNIQUE,
    temperatura_minima_c NUMERIC(5, 2),
    temperatura_maxima_c NUMERIC(5, 2),
    temperatura_detectada_c NUMERIC(5, 2),
    tipo_clima TEXT NOT NULL,
    cielo_despejado BOOLEAN,
    probabilidad_lluvia_porcentaje NUMERIC(5, 2),
    lluvia_detectada BOOLEAN,
    precipitacion_mm NUMERIC(6, 2),
    velocidad_viento_kmh NUMERIC(6, 2),
    direccion_viento TEXT,
    humedad_porcentaje NUMERIC(5, 2),
    fuente TEXT NOT NULL
);
"""

COLUMNAS_LABOR = [
    "labor", "unidad", "nombre", "tipo", "tipo_suelo", "angulo_talud", "riesgo_geotecnico", "peligros_conocidos",
    "tareas_restringidas", "controles_requeridos", "ultima_inspeccion",
]


def semilla(nombre: str = "labores") -> list[dict]:
    return json.loads((DATA_DIR / "synthetic" / f"{nombre}.json").read_text(encoding="utf-8"))


class RepoMemoria:
    def __init__(self, filas: list[dict]):
        self.filas = {f["labor"]: f for f in filas}

    def obtener(self, labor: str) -> dict | None:
        return self.filas.get(labor)


class RepoPostgres:
    def __init__(self, url: str):
        self.pool = ConnectionPool(url, kwargs={"row_factory": dict_row}, open=True)
        with self.pool.connection() as conexion:
            conexion.execute(ESQUEMA)
            if conexion.execute("SELECT count(*) AS n FROM labores").fetchone()["n"] == 0:
                with conexion.cursor() as cursor:
                    cursor.executemany(
                        f"INSERT INTO labores ({', '.join(COLUMNAS_LABOR)}) "
                        f"VALUES ({', '.join(f'%({c})s' for c in COLUMNAS_LABOR)}) ON CONFLICT (labor) DO NOTHING",
                        semilla(),
                    )
                    cursor.executemany(
                        "INSERT INTO condiciones_labor "
                        "(labor, co_ppm, o2_pct, ventilacion, ruido_dba, ultimo_desatado_h) "
                        "VALUES (%(labor)s, %(co_ppm)s, %(o2_pct)s, %(ventilacion)s, "
                        "%(ruido_dBA)s, %(ultimo_desatado_h)s) ON CONFLICT (labor) DO NOTHING",
                        semilla(),
                    )
            if conexion.execute("SELECT count(*) AS n FROM clima").fetchone()["n"] == 0:
                clima = semilla("clima")
                with conexion.cursor() as cursor:
                    cursor.executemany(
                        f"INSERT INTO clima ({', '.join(clima[0])}) "
                        f"VALUES ({', '.join(f'%({c})s' for c in clima[0])}) ON CONFLICT (clima_id) DO NOTHING",
                        clima,
                    )

    def obtener(self, labor: str) -> dict | None:
        with self.pool.connection() as conexion:
            fila = conexion.execute(
                "SELECT labor, co_ppm, o2_pct, ventilacion, ruido_dba AS \"ruido_dBA\", ultimo_desatado_h "
                "FROM condiciones_labor WHERE labor = %s",
                (labor,),
            ).fetchone()
        return fila
