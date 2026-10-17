FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app PORT=8000
WORKDIR /app
COPY agents/gemelo/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY contracts/ contracts/
COPY agents/__init__.py agents/__init__.py
COPY agents/comun/ agents/comun/
COPY agents/gemelo/ agents/gemelo/
COPY data/sheets/reglas_zona_clinica.csv data/sheets/
COPY data/synthetic/gemelos_clinicos.json data/synthetic/
RUN useradd --create-home vigia
USER vigia
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn agents.gemelo.app:app --host 0.0.0.0 --port ${PORT}"]
