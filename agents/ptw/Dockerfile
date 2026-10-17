FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app PORT=8000
WORKDIR /app
COPY agents/ptw/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY contracts/ contracts/
COPY agents/__init__.py agents/__init__.py
COPY agents/comun/ agents/comun/
COPY agents/ptw/ agents/ptw/
COPY data/sheets/limites_area.csv data/sheets/
COPY data/sheets/controles_iperc.csv data/sheets/
RUN useradd --create-home vigia
USER vigia
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn agents.ptw.app:app --host 0.0.0.0 --port ${PORT}"]
