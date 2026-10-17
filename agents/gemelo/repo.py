"""Gemelo del trabajador. Vive en su propia BD (proyecto `clinica`); nada de aqui sale del servicio.

En Postgres cada fila se guarda seudonimizada y cifrada: la clave primaria es un HMAC del
trabajador_id y el resto (identidad, sueno, datos clinicos) va cifrado con AES-GCM, con el
seudonimo como dato asociado para que una fila no pueda moverse a otra persona. Sin
CLINICA_CLAVE, ni la base ni quien la administre sabe quien es ni que tiene.
"""

import base64
import hashlib
import hmac
import json
import logging
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agents.comun.sheets import DATA_DIR

log = logging.getLogger(__name__)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS gemelos_cifrados (
    seudonimo TEXT PRIMARY KEY,
    datos BYTEA NOT NULL,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def semilla() -> list[dict]:
    return json.loads((DATA_DIR / "synthetic" / "gemelos_clinicos.json").read_text(encoding="utf-8"))


def _derivar(maestra: bytes, uso: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=uso).derive(maestra)


class Cofre:
    def __init__(self, clave_b64: str | None):
        if clave_b64:
            maestra = base64.b64decode(clave_b64)
        else:
            log.warning("CLINICA_CLAVE no definida: clave de desarrollo (solo para local)")
            maestra = hashlib.sha256(b"vigia-dev:clinica").digest()
        self._clave_seudonimo = _derivar(maestra, b"vigia-seudonimo")
        self._aes = AESGCM(_derivar(maestra, b"vigia-cifrado"))

    def seudonimo(self, trabajador_id: str) -> str:
        return hmac.new(self._clave_seudonimo, trabajador_id.encode(), hashlib.sha256).hexdigest()

    def cifrar(self, seudonimo: str, fila: dict) -> bytes:
        nonce = os.urandom(12)
        return nonce + self._aes.encrypt(nonce, json.dumps(fila, ensure_ascii=False).encode(), seudonimo.encode())

    def descifrar(self, seudonimo: str, datos: bytes) -> dict:
        return json.loads(self._aes.decrypt(datos[:12], datos[12:], seudonimo.encode()))


class RepoMemoria:
    def __init__(self, filas: list[dict]):
        self.filas = {f["trabajador_id"]: f for f in filas}

    def obtener(self, trabajador_id: str) -> dict | None:
        return self.filas.get(trabajador_id)


class RepoPostgres:
    def __init__(self, url: str):
        self.cofre = Cofre(os.getenv("CLINICA_CLAVE"))
        self.pool = ConnectionPool(url, kwargs={"row_factory": dict_row}, open=True)
        with self.pool.connection() as conexion:
            conexion.execute(ESQUEMA)
            if conexion.execute("SELECT count(*) AS n FROM gemelos_cifrados").fetchone()["n"] == 0:
                filas = [(self.cofre.seudonimo(f["trabajador_id"]), f) for f in semilla()]
                with conexion.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO gemelos_cifrados (seudonimo, datos) VALUES (%s, %s) ON CONFLICT (seudonimo) DO NOTHING",
                        [(s, self.cofre.cifrar(s, f)) for s, f in filas],
                    )

    def obtener(self, trabajador_id: str) -> dict | None:
        seudonimo = self.cofre.seudonimo(trabajador_id)
        with self.pool.connection() as conexion:
            fila = conexion.execute(
                "SELECT datos FROM gemelos_cifrados WHERE seudonimo = %s", (seudonimo,)
            ).fetchone()
        return self.cofre.descifrar(seudonimo, fila["datos"]) if fila else None
