"""Energia visible del avatar (0-100), calculada con reglas a partir de sueno_h y dia_rotacion."""

# (horas de sueno minimas, puntos base): se toma la primera fila que se cumple.
PUNTOS_SUENO = [(7, 90), (6, 70), (5, 50), (4, 35), (0, 20)]

# (fraccion de la rotacion transcurrida maxima, descuento)
DESCUENTO_ROTACION = [(0.25, 5), (0.5, 10), (1.0, 15)]


def total_rotacion(regimen_turno: str) -> int:
    """'14x7' -> 14 dias de trabajo por rotacion."""
    return int(regimen_turno.lower().split("x")[0])


def calcular_energia(sueno_h: float, dia_rotacion: int, total: int) -> int:
    base = next(puntos for minimo, puntos in PUNTOS_SUENO if sueno_h >= minimo)
    fraccion = dia_rotacion / total
    descuento = next((d for tope, d in DESCUENTO_ROTACION if fraccion <= tope), DESCUENTO_ROTACION[-1][1])
    return max(0, min(100, base - descuento))
