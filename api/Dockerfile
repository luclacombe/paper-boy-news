FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY api/ /app/api/

ENV PYTHONPATH=/app/src:/app

RUN useradd --create-home --shell /bin/bash appuser
USER appuser

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
