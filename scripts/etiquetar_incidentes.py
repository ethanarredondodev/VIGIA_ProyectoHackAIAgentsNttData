"""Etiqueta reportes de incidentes en texto libre con Claude Haiku usando la Message Batches API.

Se ejecuta UNA sola vez por lote de reportes: el agente de incidentes luego filtra por
estas columnas estructuradas, sin embeddings.

Entrada: CSV con una columna de texto (por defecto `descripcion`). Todas las columnas de
la fila se envian como contexto (en Kaggle sirven `Critical Risk` y `Potential Accident Level`).
Salida: JSON con las columnas de la tabla `incidentes`, o insercion directa con --database-url.

Ejemplos:
  python scripts/etiquetar_incidentes.py --entrada data/synthetic/incidentes_raw.csv \\
      --salida data/synthetic/incidentes_claude.json
  python scripts/etiquetar_incidentes.py --entrada data/raw/IHMStefanini_industrial_safety_and_health_database_with_accidents_description.csv \\
      --columna-texto Description --columna-id "" --filtro "Industry Sector=Mining" --origen kaggle --limite 200
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic  # noqa: E402
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming  # noqa: E402
from anthropic.types.messages.batch_create_params import Request  # noqa: E402

from contracts.vocabulario import POTENCIALES, RIESGOS_CRITICOS, TIPOS_LABOR, TIPOS_TAREA  # noqa: E402

MODELO = "claude-haiku-5-5"
ETIQUETAS = ["tipo_mineria", "tipo_tarea", "labor_tipo", "turno", "riesgo_critico", "causa_probable",
             "potencial", "resumen_es"]

ESQUEMA = {
    "type": "object",
    "properties": {
        "tipo_mineria": {"type": "string", "enum": ["subterranea", "tajo_abierto"]},
        "tipo_tarea": {"type": "string", "enum": TIPOS_TAREA},
        "labor_tipo": {"type": "string", "enum": TIPOS_LABOR},
        "turno": {"type": "string", "enum": ["dia", "noche"]},
        "riesgo_critico": {"type": "string", "enum": RIESGOS_CRITICOS},
        "causa_probable": {"type": "string"},
        "potencial": {"type": "string", "enum": POTENCIALES},
        "resumen_es": {"type": "string"},
    },
    "required": ETIQUETAS,
    "additionalProperties": False,
}

SISTEMA = (
    "Eres un especialista en seguridad minera en Peru. Recibes un reporte de incidente (JSON con el "
    "texto y metadatos) y lo clasificas en las columnas pedidas. Reglas: usa solo los valores "
    "permitidos; si el reporte no indica un dato, elige el valor mas probable segun el texto. "
    "`causa_probable`: una frase corta en espanol. `resumen_es`: una o dos oraciones en espanol "
    "neutro, sin nombres de personas. `potencial`: gravedad que pudo tener el evento (no la real)."
)


def leer_filas(ruta: Path, columna_texto: str, filtro: str | None, limite: int | None) -> list[dict]:
    with ruta.open(encoding="utf-8-sig") as f:
        filas = [fila for fila in csv.DictReader(f) if fila.get(columna_texto, "").strip()]
    if filtro:
        columna, valor = filtro.split("=", 1)
        filas = [fila for fila in filas if fila.get(columna) == valor]
    return filas[:limite] if limite else filas


def crear_lote(cliente: anthropic.Anthropic, filas: dict[str, dict], modelo: str) -> str:
    peticiones = [
        Request(
            custom_id=custom_id,
            params=MessageCreateParamsNonStreaming(
                model=modelo,
                max_tokens=2048,
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
                system=SISTEMA,
                messages=[{"role": "user", "content": json.dumps(fila, ensure_ascii=False)}],
            ),
        )
        for custom_id, fila in filas.items()
    ]
    lote = cliente.messages.batches.create(requests=peticiones)
    print(f"Lote {lote.id} creado con {len(peticiones)} reportes")
    return lote.id


def esperar(cliente: anthropic.Anthropic, lote_id: str) -> None:
    while True:
        lote = cliente.messages.batches.retrieve(lote_id)
        if lote.processing_status == "ended":
            conteo = lote.request_counts
            print(f"Lote terminado: {conteo.succeeded} ok, {conteo.errored} con error, {conteo.expired} expirados")
            return
        print(f"  {lote.processing_status}: {lote.request_counts.processing} en proceso...")
        time.sleep(30)


def recoger(cliente: anthropic.Anthropic, lote_id: str, filas: dict[str, dict], args) -> list[dict]:
    etiquetados = []
    for resultado in cliente.messages.batches.results(lote_id):
        if resultado.result.type != "succeeded":
            print(f"  {resultado.custom_id}: {resultado.result.type}, se omite")
            continue
        mensaje = resultado.result.message
        if mensaje.stop_reason != "end_turn":
            print(f"  {resultado.custom_id}: stop_reason={mensaje.stop_reason}, se omite")
            continue
        etiquetas = json.loads(next(b.text for b in mensaje.content if b.type == "text"))
        fila = filas[resultado.custom_id]
        etiquetados.append({
            "id": fila.get(args.columna_id) or resultado.custom_id,
            "fecha": (fila.get(args.columna_fecha) or date.today().isoformat())[:10],
            "unidad": fila.get("unidad", ""),
            **{k: etiquetas[k] for k in ETIQUETAS},
            "origen": args.origen,
        })
    return sorted(etiquetados, key=lambda e: e["id"])


def guardar_en_postgres(url: str, etiquetados: list[dict]) -> None:
    import psycopg

    from agents.incidentes.repo import COLUMNAS, ESQUEMA as ESQUEMA_SQL

    with psycopg.connect(url) as conexion:
        conexion.execute(ESQUEMA_SQL)
        with conexion.cursor() as cursor:
            cursor.executemany(
                f"INSERT INTO incidentes ({', '.join(COLUMNAS)}) VALUES ({', '.join(f'%({c})s' for c in COLUMNAS)}) "
                "ON CONFLICT (id) DO NOTHING",
                etiquetados,
            )
    print(f"{len(etiquetados)} incidentes insertados en Postgres")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entrada", type=Path, required=True)
    parser.add_argument("--salida", type=Path, default=Path("data/synthetic/incidentes_claude.json"))
    parser.add_argument("--database-url", default=None, help="Inserta en la tabla incidentes en vez de escribir JSON")
    parser.add_argument("--columna-texto", default="descripcion")
    parser.add_argument("--columna-id", default="id", help='"" para numerar las filas')
    parser.add_argument("--columna-fecha", default="fecha")
    parser.add_argument("--filtro", default=None, help="COLUMNA=VALOR para etiquetar solo algunas filas")
    parser.add_argument("--origen", default="reporte")
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--modelo", default=MODELO)
    parser.add_argument("--lote", default=None, help="Retoma un lote ya creado (id msgbatch_...)")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Define ANTHROPIC_API_KEY para etiquetar con Claude")
    filas = {
        f"fila-{i:05d}": fila
        for i, fila in enumerate(leer_filas(args.entrada, args.columna_texto, args.filtro, args.limite))
    }
    if not filas:
        sys.exit(f"No hay filas con texto en la columna {args.columna_texto!r}")

    cliente = anthropic.Anthropic()
    lote_id = args.lote or crear_lote(cliente, filas, args.modelo)
    esperar(cliente, lote_id)
    etiquetados = recoger(cliente, lote_id, filas, args)

    if args.database_url:
        guardar_en_postgres(args.database_url, etiquetados)
    else:
        args.salida.write_text(json.dumps(etiquetados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{len(etiquetados)} incidentes etiquetados en {args.salida}")


if __name__ == "__main__":
    main()
