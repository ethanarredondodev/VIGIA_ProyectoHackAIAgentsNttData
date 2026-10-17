FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8501
WORKDIR /app
COPY ui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY ui/ ui/
COPY data/synthetic/solicitudes.json data/synthetic/
COPY data/sheets/fuentes.csv data/sheets/
RUN useradd --create-home vigia
USER vigia
EXPOSE 8501
CMD ["sh", "-c", "exec streamlit run ui/app.py --server.port ${PORT} --server.address 0.0.0.0 --browser.gatherUsageStats false"]
