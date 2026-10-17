FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app PORT=8000
WORKDIR /app
COPY agents/area/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY contracts/ contracts/
COPY agents/__init__.py agents/__init__.py
COPY agents/comun/ agents/comun/
COPY agents/area/ agents/area/
COPY data/synthetic/labores.json data/synthetic/clima.json data/synthetic/
RUN useradd --create-home vigia
USER vigia
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn agents.area.app:app --host 0.0.0.0 --port ${PORT}"]
