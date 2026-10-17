import pytest


@pytest.fixture(autouse=True)
def entorno_aislado(monkeypatch):
    """Los tests no tocan Postgres, NANDA ni la API de Claude: usan memoria y textos de respaldo."""
    for variable in ("DATABASE_URL", "NANDA_URL", "ANTHROPIC_API_KEY", "LANGFUSE_PUBLIC_KEY", "MOCK_MODE"):
        monkeypatch.delenv(variable, raising=False)
