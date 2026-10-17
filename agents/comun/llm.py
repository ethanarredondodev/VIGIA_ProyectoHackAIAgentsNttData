"""Cliente minimo de Claude. Solo resume y redacta: nunca decide el nivel de riesgo."""

import logging
import os

import anthropic

log = logging.getLogger(__name__)

MODELO_REDACCION = "claude-sonnet-5-5"


def redactar(sistema: str, contenido: str, max_tokens: int = 4000) -> str | None:
    """Devuelve el texto de Claude Sonnet o None si no hay credenciales o la llamada falla.

    El llamador siempre tiene un texto determinista de respaldo.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    cliente = anthropic.Anthropic(timeout=30.0, max_retries=1)
    try:
        respuesta = cliente.beta.messages.create(
            model=os.getenv("MODELO_REDACCION", MODELO_REDACCION),
            max_tokens=max_tokens,
            output_config={"effort": "low"},
            system=sistema,
            messages=[{"role": "user", "content": contenido}],
            # Si el clasificador de seguridad rechaza, la API reintenta en el modelo recomendado.
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
    except anthropic.APIError as e:
        log.warning("Claude no disponible, se usa texto de respaldo: %s", e)
        return None
    if respuesta.stop_reason == "refusal":
        log.warning("Claude rechazo la solicitud, se usa texto de respaldo")
        return None
    texto = "".join(b.text for b in respuesta.content if b.type == "text").strip()
    return texto or None
