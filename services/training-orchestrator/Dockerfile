FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/python/ /app/shared/python/
COPY services/training-orchestrator/requirements.txt /app/services/training-orchestrator/requirements.txt

RUN pip install --no-cache-dir -r /app/services/training-orchestrator/requirements.txt
RUN pip install --no-cache-dir -e /app/shared/python/

COPY services/training-orchestrator/orchestrator_app /app/services/training-orchestrator/orchestrator_app

WORKDIR /app/services/training-orchestrator

EXPOSE 8084

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8084/health || exit 1

ENTRYPOINT ["uvicorn", "orchestrator_app.main:app", "--host", "0.0.0.0", "--port", "8084"]
