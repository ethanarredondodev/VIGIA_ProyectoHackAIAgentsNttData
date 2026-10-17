"""Condiciones actuales de cada labor. Postgres (proyecto `operacion`) o memoria si no hay DATABASE_URL."""

import json

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agents.comun.sheets import DATA_DIR

ESQUEMA = """
CREATE TABLE IF NOT EXISTS condiciones_labor (
    labor TEXT PRIMARY KEY,
    unidad TEXT NOT NULL DEFAULT '',
    co_ppm DOUBLE PRECISION NOT NULL,
    o2_pct DOUBLE PRECISION NOT NULL,
    ventilacion TEXT NOT NULL,
    ruido_dba DOUBLE PRECISION NOT NULL,
    ultimo_desatado_h DOUBLE PRECISION NOT NULL,
    medido_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def semilla() -> list[dict]:
    return json.loads((DATA_DIR / "synthetic" / "labores.json").read_text(encoding="utf-8"))


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
            if conexion.execute("SELECT count(*) AS n FROM condiciones_labor").fetchone()["n"] == 0:
                with conexion.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO condiciones_labor "
                        "(labor, unidad, co_ppm, o2_pct, ventilacion, ruido_dba, ultimo_desatado_h) "
                        "VALUES (%(labor)s, %(unidad)s, %(co_ppm)s, %(o2_pct)s, %(ventilacion)s, "
                        "%(ruido_dBA)s, %(ultimo_desatado_h)s) ON CONFLICT (labor) DO NOTHING",
                        semilla(),
                    )

    def obtener(self, labor: str) -> dict | None:
        with self.pool.connection() as conexion:
            fila = conexion.execute(
                "SELECT labor, co_ppm, o2_pct, ventilacion, ruido_dba AS \"ruido_dBA\", ultimo_desatado_h "
                "FROM condiciones_labor WHERE labor = %s",
                (labor,),
            ).fetchone()
        return fila
