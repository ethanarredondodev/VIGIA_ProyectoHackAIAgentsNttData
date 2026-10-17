"""Padron, catalogo de trabajos, historial de trabajos, registro de cada solicitud PTW (lo que lee el front) y
bandeja del supervisor. Postgres (`operacion`) o memoria. Nada de esto tiene datos clinicos: viven solo en `clinica`.
"""

import copy
import json

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from agents.comun.sheets import DATA_DIR
from contracts.vocabulario import TIPOS_TAREA

# Sentencias separadas: el pool usa prepare_threshold=0 y no se puede preparar mas de un comando a la vez.
ESQUEMA = [
    """
    CREATE TABLE IF NOT EXISTS trabajadores (
        trabajador_id TEXT PRIMARY KEY,
        nombres TEXT NOT NULL,
        apellidos TEXT NOT NULL,
        cargo TEXT NOT NULL,
        empresa TEXT NOT NULL,
        empleador TEXT NOT NULL CHECK (empleador IN ('titular', 'contratista')),
        fecha_nacimiento DATE,
        fecha_ingreso DATE NOT NULL,
        estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'suspendido', 'inactivo'))
    )
    """,
    # TRABAJO del diagrama (hoja TRABAJO de base_datos_mineria.xlsx). tipo_tarea lo liga a reglas e incidentes.
    f"""
    CREATE TABLE IF NOT EXISTS trabajos (
        trabajo_id INTEGER PRIMARY KEY,
        tipo_trabajo_minero TEXT NOT NULL,
        tipo_tarea TEXT NOT NULL CHECK (tipo_tarea IN ({", ".join(f"'{t}'" for t in TIPOS_TAREA)})),
        descripcion TEXT NOT NULL,
        nivel_riesgo TEXT NOT NULL CHECK (nivel_riesgo IN ('bajo', 'medio', 'alto', 'critico')),
        riesgos_principales TEXT NOT NULL,
        controles_requeridos TEXT,
        equipos_proteccion_personal TEXT,
        competencias_requeridas TEXT,
        procedimiento_seguro TEXT,
        requiere_autorizacion BOOLEAN NOT NULL,
        requiere_supervision BOOLEAN NOT NULL,
        estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
        fuente TEXT,
        costo NUMERIC(12, 2),
        duracion NUMERIC(10, 2),
        personas_necesarias INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ptw (
        id TEXT PRIMARY KEY,
        estado TEXT NOT NULL,
        trabajador_id TEXT NOT NULL REFERENCES trabajadores (trabajador_id),
        datos JSONB NOT NULL,
        creado_en TIMESTAMPTZ NOT NULL,
        actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ptw_estado ON ptw (estado)",
    "CREATE INDEX IF NOT EXISTS ix_ptw_trabajador ON ptw (trabajador_id)",
    # Trabajos previos a Vigia; los nuevos quedan en `ptw`. incidente_id apunta a `incidentes` (de vigia-incidentes).
    """
    CREATE TABLE IF NOT EXISTS historial_trabajos (
        historial_trabajo_id TEXT PRIMARY KEY,
        trabajador_id TEXT NOT NULL REFERENCES trabajadores (trabajador_id),
        labor TEXT NOT NULL,
        trabajo_id INTEGER REFERENCES trabajos (trabajo_id),
        incidente_id TEXT,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE,
        turno TEXT NOT NULL CHECK (turno IN ('dia', 'noche')),
        estado_trabajo TEXT NOT NULL CHECK (estado_trabajo IN ('completado', 'interrumpido', 'cancelado')),
        descripcion_realizada TEXT NOT NULL,
        observaciones TEXT NOT NULL DEFAULT '',
        validado_por TEXT,
        fecha_validacion DATE,
        costo_real NUMERIC(12, 2),
        duracion_real NUMERIC(10, 2)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_historial_trabajador ON historial_trabajos (trabajador_id)",
]

# Cada tabla se siembra desde data/synthetic/<tabla>.json, en este orden por las FK.
SEMILLAS = [("trabajadores", "trabajador_id"), ("trabajos", "trabajo_id"), ("historial_trabajos", "historial_trabajo_id")]

ESTADOS_BANDEJA = ("en_revision", "bloqueado")


def semilla(nombre: str = "trabajadores") -> list[dict]:
    return json.loads((DATA_DIR / "synthetic" / f"{nombre}.json").read_text(encoding="utf-8"))


class RepoPtwMemoria:
    def __init__(self, trabajadores: list[dict]) -> None:
        self.registros: dict[str, dict] = {}
        self.trabajadores = {t["trabajador_id"]: t for t in trabajadores}

    async def trabajador(self, trabajador_id: str) -> dict | None:
        return copy.deepcopy(self.trabajadores.get(trabajador_id))

    async def guardar(self, registro: dict) -> None:
        self.registros[registro["ptw_id"]] = copy.deepcopy(registro)

    async def obtener(self, ptw_id: str) -> dict | None:
        return copy.deepcopy(self.registros.get(ptw_id))

    async def listar(self, trabajador_id: str | None = None, estados: tuple[str, ...] | None = None) -> list[dict]:
        return sorted(
            (
                copy.deepcopy(r) for r in self.registros.values()
                if (trabajador_id is None or r["solicitud"]["trabajador_id"] == trabajador_id)
                and (estados is None or r["estado"] in estados)
            ),
            key=lambda r: r["creado_en"],
            reverse=True,
        )


class RepoPtwPostgres:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self.pool = pool

    async def preparar(self) -> None:
        async with self.pool.connection() as conexion:
            for sentencia in ESQUEMA:
                await conexion.execute(sentencia)
            for tabla, clave in SEMILLAS:
                if (await (await conexion.execute(f"SELECT count(*) AS n FROM {tabla}")).fetchone())["n"] == 0:
                    filas = semilla(tabla)
                    async with conexion.cursor() as cursor:
                        await cursor.executemany(
                            f"INSERT INTO {tabla} ({', '.join(filas[0])}) "
                            f"VALUES ({', '.join(f'%({c})s' for c in filas[0])}) ON CONFLICT ({clave}) DO NOTHING",
                            filas,
                        )

    async def trabajador(self, trabajador_id: str) -> dict | None:
        async with self.pool.connection() as conexion:
            cursor = await conexion.execute("SELECT * FROM trabajadores WHERE trabajador_id = %s", (trabajador_id,))
            return await cursor.fetchone()

    async def guardar(self, registro: dict) -> None:
        async with self.pool.connection() as conexion:
            await conexion.execute(
                """
                INSERT INTO ptw (id, estado, trabajador_id, datos, creado_en)
                VALUES (%(id)s, %(estado)s, %(trabajador_id)s, %(datos)s, %(creado_en)s)
                ON CONFLICT (id) DO UPDATE SET estado = EXCLUDED.estado, datos = EXCLUDED.datos, actualizado_en = now()
                """,
                {
                    "id": registro["ptw_id"],
                    "estado": registro["estado"],
                    "trabajador_id": registro["solicitud"]["trabajador_id"],
                    "datos": Jsonb(registro),
                    "creado_en": registro["creado_en"],
                },
            )

    async def obtener(self, ptw_id: str) -> dict | None:
        async with self.pool.connection() as conexion:
            fila = await (await conexion.execute("SELECT datos FROM ptw WHERE id = %s", (ptw_id,))).fetchone()
        return fila["datos"] if fila else None

    async def listar(self, trabajador_id: str | None = None, estados: tuple[str, ...] | None = None) -> list[dict]:
        async with self.pool.connection() as conexion:
            cursor = await conexion.execute(
                """
                SELECT datos FROM ptw
                WHERE (%(trabajador_id)s::text IS NULL OR trabajador_id = %(trabajador_id)s)
                  AND (%(estados)s::text[] IS NULL OR estado = ANY(%(estados)s))
                ORDER BY creado_en DESC LIMIT 200
                """,
                {"trabajador_id": trabajador_id, "estados": list(estados) if estados else None},
            )
            filas = await cursor.fetchall()
        return [f["datos"] for f in filas]
