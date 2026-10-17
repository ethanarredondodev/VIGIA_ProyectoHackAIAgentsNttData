"""Gemelo del trabajador. Vive en su propia BD (proyecto `clinica`); nada de aqui sale del servicio."""

import json

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from agents.comun.sheets import DATA_DIR

ESQUEMA = """
CREATE TABLE IF NOT EXISTS gemelos (
    trabajador_id TEXT PRIMARY KEY,
    sueno_h DOUBLE PRECISION NOT NULL,
    dia_rotacion INTEGER NOT NULL,
    regimen_turno TEXT NOT NULL,
    exposicion_silice TEXT NOT NULL,
    datos_clinicos JSONB NOT NULL DEFAULT '{}'::jsonb,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def semilla() -> list[dict]:
    return json.loads((DATA_DIR / "synthetic" / "gemelos_clinicos.json").read_text(encoding="utf-8"))


class RepoMemoria:
    def __init__(self, filas: list[dict]):
        self.filas = {f["trabajador_id"]: f for f in filas}

    def obtener(self, trabajador_id: str) -> dict | None:
        return self.filas.get(trabajador_id)


class RepoPostgres:
    def __init__(self, url: str):
        self.pool = ConnectionPool(url, kwargs={"row_factory": dict_row}, open=True)
        with self.pool.connection() as conexion:
            conexion.execute(ESQUEMA)
            if conexion.execute("SELECT count(*) AS n FROM gemelos").fetchone()["n"] == 0:
                with conexion.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO gemelos (trabajador_id, sueno_h, dia_rotacion, regimen_turno, "
                        "exposicion_silice, datos_clinicos) VALUES (%(trabajador_id)s, %(sueno_h)s, "
                        "%(dia_rotacion)s, %(regimen_turno)s, %(exposicion_silice)s, %(datos_clinicos)s) "
                        "ON CONFLICT (trabajador_id) DO NOTHING",
                        [{**f, "datos_clinicos": Jsonb(f["datos_clinicos"])} for f in semilla()],
                    )

    def obtener(self, trabajador_id: str) -> dict | None:
        with self.pool.connection() as conexion:
            return conexion.execute("SELECT * FROM gemelos WHERE trabajador_id = %s", (trabajador_id,)).fetchone()
