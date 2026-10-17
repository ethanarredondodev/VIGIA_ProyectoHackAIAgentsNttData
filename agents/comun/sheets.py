"""Tablas de reglas leidas de CSV exportados de Google Sheets.

Si existe la variable SHEETS_<NOMBRE>_URL (URL de "Publicar en la web > CSV"),
se descarga de ahi; si no, se usan las filas de ejemplo de data/sheets/.
Se recargan cada SHEETS_RECARGA_S segundos (300 por defecto).
"""

import csv
import io
import logging
import os
import threading
import time
from pathlib import Path

import httpx

from agents.comun.reglas import parsear_disparador
from contracts.vocabulario import SENALES_DERIVADAS, VARIABLES_PERMITIDAS

log = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

COLUMNAS = {
    "reglas_zona_clinica": [
        "id", "variable", "operador", "umbral", "unidad", "resultado",
        "motivo_visible", "base_legal", "fuente", "estado",
    ],
    "limites_area": ["id", "agente", "limite", "unidad", "tipo", "tipo_mineria", "base_legal", "fuente", "estado"],
    "controles_iperc": [
        "id", "riesgo_critico", "trabajo_alto_riesgo", "disparador", "control", "jerarquia", "base_legal", "fuente",
    ],
    "unidades_mineras": [
        "unidad", "empresa", "region", "tipo_mineria", "estrato", "altitud_msnm", "regimen_turno", "fuente",
    ],
    "fuentes": ["id", "titulo", "link", "origen", "dato_que_aporta", "fecha_consulta"],
}


def _fila_valida(nombre: str, fila: dict) -> bool:
    if nombre == "reglas_zona_clinica":
        return fila["variable"] in VARIABLES_PERMITIDAS
    if nombre == "limites_area":
        return fila["agente"] in VARIABLES_PERMITIDAS
    if nombre == "controles_iperc":
        try:
            disparador = parsear_disparador(fila["disparador"])
        except ValueError:
            return False
        return disparador is None or disparador[0] in VARIABLES_PERMITIDAS | SENALES_DERIVADAS
    return True


class TablaSheets:
    def __init__(self, nombre: str):
        self.nombre = nombre
        self._filas: list[dict] = []
        self._cargada_en = 0.0
        self._candado = threading.Lock()

    def filas(self) -> list[dict]:
        recarga_s = int(os.getenv("SHEETS_RECARGA_S", "300"))
        with self._candado:
            if not self._filas or time.monotonic() - self._cargada_en > recarga_s:
                try:
                    self._filas = self._leer()
                except (httpx.HTTPError, ValueError) as e:
                    if not self._filas:
                        raise
                    log.warning("No se pudo recargar %s, se mantienen las filas previas: %s", self.nombre, e)
                self._cargada_en = time.monotonic()
            return self._filas

    def _leer(self) -> list[dict]:
        url = os.getenv(f"SHEETS_{self.nombre.upper()}_URL")
        if url:
            respuesta = httpx.get(url, timeout=10, follow_redirects=True)
            respuesta.raise_for_status()
            texto = respuesta.text
        else:
            texto = (DATA_DIR / "sheets" / f"{self.nombre}.csv").read_text(encoding="utf-8")
        lector = csv.DictReader(io.StringIO(texto))
        if lector.fieldnames != COLUMNAS[self.nombre]:
            raise ValueError(f"{self.nombre}: columnas {lector.fieldnames} != {COLUMNAS[self.nombre]}")
        filas = []
        for fila in lector:
            if _fila_valida(self.nombre, fila):
                filas.append({k: v.strip() for k, v in fila.items()})
            else:
                log.warning("%s: fila %s usa una variable no permitida, se ignora", self.nombre, fila.get("id"))
        return filas


def activas(filas: list[dict]) -> list[dict]:
    return [f for f in filas if f.get("estado", "") != "inactiva"]
