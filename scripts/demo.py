"""Caso de demo de Juan de punta a punta contra el stack local (docker compose up).

Solo usa la libreria estandar para correr en cualquier maquina.
Uso: python scripts/demo.py [--ptw http://localhost:8000]
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MOCKS = Path(__file__).resolve().parents[1] / "contracts" / "mocks"


def llamar(metodo: str, url: str, cuerpo: dict | None = None) -> dict:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(url, data=datos, method=metodo, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=180) as respuesta:
        return json.loads(respuesta.read())


def esperar_ptw(ptw: str, segundos: int = 120) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        try:
            llamar("GET", f"{ptw}/health")
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(2)
    sys.exit(f"El orquestador PTW no respondio en {ptw} tras {segundos} s. Revisa: docker compose logs ptw")


def mock(nombre: str) -> dict:
    return json.loads((MOCKS / f"{nombre}.json").read_text(encoding="utf-8"))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--ptw", default="http://localhost:8000")
    ptw = parser.parse_args().ptw.rstrip("/")
    esperar_ptw(ptw)

    solicitud = mock("ptw_solicitud")
    print(f"1) Juan (T-001) solicita: {solicitud['tarea']} en {solicitud['labor']}, turno {solicitud['turno']}, "
          f"{solicitud['altitud_msnm']} msnm")
    petar = llamar("POST", f"{ptw}/ptw/solicitud", solicitud)
    propuesta = petar["propuesta"]
    print(f"   {petar['id']}: nivel {propuesta['nivel'].upper()} -> {propuesta['decision']}")
    print("   Por qué:")
    for motivo in propuesta["porque"]:
        print(f"     - {motivo}")
    print("   Controles extra:")
    for control in propuesta["controles_extra"]:
        print(f"     - {control}")
    print(f"   Alternativa: {propuesta['alternativa']}")
    print(f"   Explicación: {petar['explicacion']}")
    if petar["errores"]:
        print(f"   Avisos de agentes: {petar['errores']}")
    if (propuesta["nivel"], propuesta["decision"]) != ("ambar", "autorizar_con_controles"):
        sys.exit("ERROR: se esperaba ambar / autorizar_con_controles para el caso de Juan")

    firma = mock("firma")
    print(f"2) {firma['supervisor']} firma: {firma['accion']}")
    firmado = llamar("POST", f"{ptw}/ptw/{petar['id']}/firma", firma)
    print(f"   Estado: {firmado['estado']} con {len(firmado['firma']['controles_finales'])} controles")

    resultado = mock("resultado")
    print(f"3) Fin de la tarea: {resultado['resultado']}")
    cerrado = llamar("POST", f"{ptw}/ptw/{petar['id']}/resultado", resultado)
    print(f"   Estado: {cerrado['estado']}. El resultado quedó en el historial.")
    print("OK: caso de Juan completado de punta a punta.")


if __name__ == "__main__":
    main()
