"""Registro de PETAR para la vista del supervisor y el historial. Postgres (`operacion`) o memoria."""

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from contracts.modelos import Petar

ESQUEMA = """
CREATE TABLE IF NOT EXISTS petar (
    id TEXT PRIMARY KEY,
    estado TEXT NOT NULL,
    trabajador_id TEXT NOT NULL,
    datos JSONB NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_petar_estado ON petar (estado);
"""


class RepoPetarMemoria:
    def __init__(self) -> None:
        self.petars: dict[str, Petar] = {}

    async def guardar(self, petar: Petar) -> None:
        self.petars[petar.id] = petar

    async def obtener(self, petar_id: str) -> Petar | None:
        return self.petars.get(petar_id)

    async def listar(self, estado: str | None = None, trabajador_id: str | None = None) -> list[Petar]:
        return sorted(
            (
                p for p in self.petars.values()
                if (estado is None or p.estado == estado)
                and (trabajador_id is None or p.solicitud.trabajador_id == trabajador_id)
            ),
            key=lambda p: p.creado_en,
            reverse=True,
        )


class RepoPetarPostgres:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self.pool = pool

    async def preparar(self) -> None:
        async with self.pool.connection() as conexion:
            await conexion.execute(ESQUEMA)

    async def guardar(self, petar: Petar) -> None:
        async with self.pool.connection() as conexion:
            await conexion.execute(
                """
                INSERT INTO petar (id, estado, trabajador_id, datos, creado_en, actualizado_en)
                VALUES (%(id)s, %(estado)s, %(trabajador_id)s, %(datos)s, %(creado_en)s, %(actualizado_en)s)
                ON CONFLICT (id) DO UPDATE SET estado = EXCLUDED.estado, datos = EXCLUDED.datos,
                    actualizado_en = EXCLUDED.actualizado_en
                """,
                {
                    "id": petar.id,
                    "estado": petar.estado,
                    "trabajador_id": petar.solicitud.trabajador_id,
                    "datos": Jsonb(petar.model_dump(mode="json")),
                    "creado_en": petar.creado_en,
                    "actualizado_en": petar.actualizado_en,
                },
            )

    async def obtener(self, petar_id: str) -> Petar | None:
        async with self.pool.connection() as conexion:
            fila = await (await conexion.execute("SELECT datos FROM petar WHERE id = %s", (petar_id,))).fetchone()
        return Petar.model_validate(fila["datos"]) if fila else None

    async def listar(self, estado: str | None = None, trabajador_id: str | None = None) -> list[Petar]:
        async with self.pool.connection() as conexion:
            cursor = await conexion.execute(
                """
                SELECT datos FROM petar
                WHERE (%(estado)s::text IS NULL OR estado = %(estado)s)
                  AND (%(trabajador_id)s::text IS NULL OR trabajador_id = %(trabajador_id)s)
                ORDER BY creado_en DESC LIMIT 200
                """,
                {"estado": estado, "trabajador_id": trabajador_id},
            )
            filas = await cursor.fetchall()
        return [Petar.model_validate(f["datos"]) for f in filas]
