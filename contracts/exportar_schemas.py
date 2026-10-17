"""Exporta cada contrato a contracts/schemas/<Modelo>.json.

Uso: python -m contracts.exportar_schemas
"""

import json
from pathlib import Path

from contracts.agent_facts import AgentFactsFirmadas
from contracts.modelos import CONTRATOS

DIRECTORIO = Path(__file__).parent / "schemas"


def schemas() -> dict[str, str]:
    return {
        modelo.__name__: json.dumps(modelo.model_json_schema(), indent=2, ensure_ascii=False) + "\n"
        for modelo in [*CONTRATOS, AgentFactsFirmadas]
    }


if __name__ == "__main__":
    DIRECTORIO.mkdir(exist_ok=True)
    for nombre, contenido in schemas().items():
        (DIRECTORIO / f"{nombre}.json").write_text(contenido, encoding="utf-8")
        print(f"contracts/schemas/{nombre}.json")
