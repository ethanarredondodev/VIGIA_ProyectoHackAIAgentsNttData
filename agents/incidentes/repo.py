"""Historial de incidentes etiquetados. Postgres (proyecto `operacion`) o memoria si no hay DATABASE_URL."""

import json

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agents.comun.sheets import DATA_DIR

ORDEN_POTENCIAL = ["critico", "alto", "medio", "bajo"]

COLUMNAS = [
    "id", "fecha", "unidad", "tipo_mineria", "tipo_tarea", "labor_tipo", "turno",
    "riesgo_critico", "causa_probable", "potencial", "resumen_es", "origen",
]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS incidentes (
    id TEXT PRIMARY KEY,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    unidad TEXT NOT NULL DEFAULT '',
    tipo_mineria TEXT NOT NULL,
    tipo_tarea TEXT NOT NULL,
    labor_tipo TEXT NOT NULL,
    turno TEXT NOT NULL,
    riesgo_critico TEXT NOT NULL,
    causa_probable TEXT NOT NULL,
    potencial TEXT NOT NULL,
    resumen_es TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'sintetico'
);
CREATE INDEX IF NOT EXISTS ix_incidentes_filtro ON incidentes (tipo_mineria, tipo_tarea, labor_tipo, turno);
"""


def semilla() -> list[dict]:
    ruta = DATA_DIR / "synthetic" / "incidentes_etiquetados.json"
    return json.loads(ruta.read_text(encoding="utf-8"))


def _ordenar(filas: list[dict]) -> list[dict]:
    por_fecha = sorted(filas, key=lambda f: str(f["fecha"]), reverse=True)
    return sorted(por_fecha, key=lambda f: ORDEN_POTENCIAL.index(f["potencial"]))


class RepoMemoria:
    def __init__(self, filas: list[dict]):
        self.filas = list(filas)

    def buscar(self, tipo_mineria: str, tipo_tarea: str, labor_tipo: str, turno: str | None) -> list[dict]:
        return _ordenar([
            f for f in self.filas
            if f["tipo_mineria"] == tipo_mineria
            and f["tipo_tarea"] == tipo_tarea
            and f["labor_tipo"] == labor_tipo
            and (turno is None or f["turno"] == turno)
        ])

    def registrar(self, fila: dict) -> None:
        self.filas.append(fila)


class RepoPostgres:
    def __init__(self, url: str):
        self.pool = ConnectionPool(url, kwargs={"row_factory": dict_row}, open=True)
        with self.pool.connection() as conexion:
            conexion.execute(ESQUEMA)
            if conexion.execute("SELECT count(*) AS n FROM incidentes").fetchone()["n"] == 0:
                with conexion.cursor() as cursor:
                    cursor.executemany(
                        f"INSERT INTO incidentes ({', '.join(COLUMNAS)}) "
                        f"VALUES ({', '.join(f'%({c})s' for c in COLUMNAS)}) ON CONFLICT (id) DO NOTHING",
                        semilla(),
                    )

    def buscar(self, tipo_mineria: str, tipo_tarea: str, labor_tipo: str, turno: str | None) -> list[dict]:
        with self.pool.connection() as conexion:
            return conexion.execute(
                """
                SELECT * FROM incidentes
                WHERE tipo_mineria = %(tipo_mineria)s AND tipo_tarea = %(tipo_tarea)s
                  AND labor_tipo = %(labor_tipo)s AND (%(turno)s::text IS NULL OR turno = %(turno)s)
                ORDER BY array_position(ARRAY['critico','alto','medio','bajo'], potencial), fecha DESC
                """,
                {"tipo_mineria": tipo_mineria, "tipo_tarea": tipo_tarea, "labor_tipo": labor_tipo, "turno": turno},
            ).fetchall()

    def registrar(self, fila: dict) -> None:
        columnas = [c for c in COLUMNAS if c in fila]
        with self.pool.connection() as conexion:
            conexion.execute(
                f"INSERT INTO incidentes ({', '.join(columnas)}) "
                f"VALUES ({', '.join(f'%({c})s' for c in columnas)}) ON CONFLICT (id) DO NOTHING",
                fila,
            )
