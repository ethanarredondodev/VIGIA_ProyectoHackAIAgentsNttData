FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app PORT=8000
WORKDIR /app
COPY nanda_index/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY contracts/ contracts/
COPY nanda_index/ nanda_index/
RUN useradd --create-home vigia
USER vigia
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn nanda_index.app:app --host 0.0.0.0 --port ${PORT}"]
