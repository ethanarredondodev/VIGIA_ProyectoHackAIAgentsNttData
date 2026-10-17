"""Casos de demo de Vigía de punta a punta contra el stack local (docker compose up).

1. Ambar: Juan, perforacion de frente de noche -> revision -> firma -> ejecucion -> cierre.
2. Verde: Juan descansado -> PETAR emitido solo -> ejecucion -> cierre.
3. Rojo: O2 18.2 % y ventilacion detenida -> tarea bloqueada y aviso al supervisor.
4. NANDA: una ficha del gemelo redirigida a un atacante -> el indice la rechaza.
5. Con --revocacion: la autoridad SSO revoca vigia-area en vivo -> el PETAR se bloquea; luego se restaura.

Solo usa la libreria estandar (la revocacion firma dentro del contenedor ptw).
Uso: python scripts/demo.py [--ptw http://localhost:8000] [--nanda http://localhost:8010] [--revocacion]
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FIRMA = json.loads((RAIZ / "contracts" / "mocks" / "firma.json").read_text(encoding="utf-8"))
RESULTADO = json.loads((RAIZ / "contracts" / "mocks" / "resultado.json").read_text(encoding="utf-8"))
CASOS = json.loads((RAIZ / "data" / "synthetic" / "solicitudes.json").read_text(encoding="utf-8"))[:3]


def llamar(metodo: str, url: str, cuerpo: dict | None = None):
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
    sys.exit(f"vigia-ptw no respondio en {ptw} tras {segundos} s. Revisa: docker compose logs vigia-ptw")


def evaluar(ptw: str, solicitud: dict) -> dict:
    ptw_id = llamar("POST", f"{ptw}/ptw/solicitud", solicitud)["ptw_id"]
    vistas = set()
    for _ in range(240):
        registro = llamar("GET", f"{ptw}/ptw/{ptw_id}")
        for agente, consulta in registro["consultas"].items():
            if consulta["estado"] != "pendiente" and agente not in vistas:
                vistas.add(agente)
                print(f"   consulta {agente}: {consulta['estado']}")
        if registro["estado"] != "procesando":
            return registro
        time.sleep(0.5)
    sys.exit(f"{ptw_id} sigue procesando despues de 2 minutos")


def mostrar(registro: dict) -> None:
    fichas = "; ".join(
        f"{a['id']} ✓ {' + '.join(a['emisores'])}" if a["firma"] == "valida" else f"{a['id']} ✗ {a['motivo']}"
        for a in registro["nanda"]
    )
    print(f"   NANDA: {fichas}")
    firmadas = [agente for agente, consulta in registro["consultas"].items() if consulta.get("evidencia")]
    print(f"   Respuestas firmadas (Ed25519): {', '.join(firmadas) or 'ninguna'}")
    propuesta = registro["propuesta"]
    print(f"   {registro['ptw_id']}: nivel {propuesta['nivel'].upper()} -> {propuesta['decision']} "
          f"(requiere supervisor: {propuesta['requiere_supervisor']}) -> estado {registro['estado']}")
    for motivo in propuesta["porque"]:
        print(f"     - {motivo}")
    if propuesta["controles_extra"]:
        print(f"   Controles extra: {'; '.join(propuesta['controles_extra'])}")
    print(f"   Alternativa: {propuesta['alternativa']}")


def comprobar(condicion: bool, mensaje: str) -> None:
    if not condicion:
        sys.exit(f"ERROR: {mensaje}")


def en_bandeja(ptw: str, ptw_id: str) -> str | None:
    return next((i["tipo"] for i in llamar("GET", f"{ptw}/ptw/bandeja") if i["ptw_id"] == ptw_id), None)


def ejecutar_y_cerrar(ptw: str, ptw_id: str) -> None:
    comprobar(llamar("POST", f"{ptw}/ptw/{ptw_id}/inicio")["estado"] == "en_ejecucion", "no paso a en_ejecucion")
    cerrado = llamar("POST", f"{ptw}/ptw/{ptw_id}/resultado", RESULTADO)
    comprobar(cerrado["estado"] == "cerrado", "no se cerro")
    print(f"   Ejecución y cierre: {RESULTADO['resultado']} -> estado {cerrado['estado']}")


def intentar_suplantacion(nanda: str) -> None:
    ficha = llamar("GET", f"{nanda}/resolve/vigia-gemelo")
    ficha["facts"]["endpoints"]["static"] = ["http://atacante.example:8000"]
    try:
        llamar("POST", f"{nanda}/register", ficha)
    except urllib.error.HTTPError as e:
        comprobar(e.code == 403, f"el índice debía responder 403 y respondió {e.code}")
        print(f"   El índice rechazó la ficha alterada: {e.code} {json.loads(e.read())['detail']}")
        return
    sys.exit("ERROR: el índice aceptó una ficha del gemelo redirigida a un atacante")


def revocar(*agentes: str) -> None:
    """Firma la lista con la clave de la autoridad SSO dentro del contenedor vigia-ptw y la publica en su NANDA_URL."""
    subprocess.run(
        ["docker", "compose", "exec", "-T", "vigia-ptw", "python", "-m", "contracts.agent_facts", "revocar", *agentes],
        cwd=RAIZ, check=True, capture_output=True,
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--ptw", default="http://localhost:8000")
    parser.add_argument("--nanda", default="http://localhost:8010")
    parser.add_argument("--revocacion", action="store_true", help="Revoca vigia-area en vivo y luego lo restaura")
    args = parser.parse_args()
    ptw, nanda = args.ptw.rstrip("/"), args.nanda.rstrip("/")
    esperar_ptw(ptw)

    ambar, verde, rojo = CASOS
    avatar = llamar("GET", f"{ptw}/trabajadores/{ambar['solicitud']['trabajador_id']}/avatar")
    visual = avatar["estado_visual"]
    print(f"Avatar: {avatar['nombre']} ({avatar['cargo']}), energía {visual['energia']}, "
          f"día {visual['dia_rotacion']} de {visual['total_rotacion']}, exposición {visual['exposicion_nivel']}")

    print(f"\n1) {ambar['caso']}")
    registro = evaluar(ptw, ambar["solicitud"])
    mostrar(registro)
    comprobar(registro["estado"] == "en_revision", "el caso ambar debe quedar en revision")
    comprobar(en_bandeja(ptw, registro["ptw_id"]) == "revision", "el caso ambar debe estar en la bandeja")
    firmado = llamar("POST", f"{ptw}/ptw/{registro['ptw_id']}/firma", FIRMA)
    comprobar(firmado["estado"] == "autorizado_con_controles", "la firma debe autorizar con controles")
    print(f"   {FIRMA['supervisor']} firma {firmado['petar']['numero']} con {len(firmado['petar']['checklist'])} controles")
    ejecutar_y_cerrar(ptw, registro["ptw_id"])

    print(f"\n2) {verde['caso']}")
    registro = evaluar(ptw, verde["solicitud"])
    mostrar(registro)
    comprobar(registro["estado"] == "emitido", "el caso verde debe emitirse solo")
    comprobar(registro["petar"]["firmado_por"] is None, "el caso verde no lleva firma")
    comprobar(en_bandeja(ptw, registro["ptw_id"]) is None, "el caso verde no debe aparecer en la bandeja")
    print(f"   {registro['petar']['numero']} emitido automáticamente con {len(registro['petar']['checklist'])} controles")
    ejecutar_y_cerrar(ptw, registro["ptw_id"])

    print(f"\n3) {rojo['caso']}")
    registro = evaluar(ptw, rojo["solicitud"])
    mostrar(registro)
    comprobar(registro["estado"] == "bloqueado", "el caso rojo debe quedar bloqueado")
    comprobar(en_bandeja(ptw, registro["ptw_id"]) == "aviso", "el caso rojo debe avisar al supervisor")
    print("   Tarea bloqueada; el supervisor recibió un aviso (sin firma).")

    print("\n4) NANDA: alguien intenta redirigir el gemelo a su servidor")
    intentar_suplantacion(nanda)

    if args.revocacion:
        print("\n5) NANDA: la autoridad SSO revoca vigia-area en vivo")
        revocar("vigia-area")
        try:
            registro = evaluar(ptw, verde["solicitud"])
            mostrar(registro)
            comprobar(registro["consultas"]["area"]["estado"] == "error", "no se debía consultar al área revocada")
            comprobar(registro["estado"] == "bloqueado", "sin condiciones verificables de la labor el PETAR se bloquea")
            print("   Sin un agente de área confiable, el PETAR queda bloqueado.")
        finally:
            revocar()
        print("   Revocación levantada: vigia-area vuelve a ser confiable.")

    print("\nOK: la demo se completó de punta a punta.")


if __name__ == "__main__":
    main()
