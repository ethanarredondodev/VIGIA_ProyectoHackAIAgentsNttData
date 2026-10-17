"""Evaluador determinista de condiciones `variable operador umbral` usado por las reglas de los CSV."""

import operator
import re

OPERADORES = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}

_DISPARADOR = re.compile(r"^(\w+)\s*(<=|>=|==|!=|<|>|in)\s*(.+)$")


def comparar(valor, operador: str, umbral: str) -> bool:
    if operador == "in":
        return str(valor) in [u.strip() for u in umbral.split("|")]
    try:
        return OPERADORES[operador](float(valor), float(umbral))
    except (TypeError, ValueError):
        return OPERADORES[operador](str(valor), umbral.strip())


def cumple(senales: dict, variable: str, operador: str, umbral: str) -> bool:
    if senales.get(variable) is None:
        return False
    return comparar(senales[variable], operador, umbral)


def parsear_disparador(texto: str) -> tuple[str, str, str] | None:
    """`ruido_dBA > 85` -> ("ruido_dBA", ">", "85"); `siempre` -> None."""
    texto = texto.strip()
    if texto == "siempre":
        return None
    coincidencia = _DISPARADOR.match(texto)
    if not coincidencia:
        raise ValueError(f"Disparador invalido: {texto!r}")
    variable, op, umbral = coincidencia.groups()
    return variable, op, umbral.strip()
