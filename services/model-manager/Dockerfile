FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/python/ /app/shared/python/
COPY services/model-manager/requirements.txt /app/services/model-manager/requirements.txt

RUN pip install --no-cache-dir -r /app/services/model-manager/requirements.txt
RUN pip install --no-cache-dir -e /app/shared/python/

COPY services/model-manager/model_app /app/services/model-manager/model_app

WORKDIR /app/services/model-manager

EXPOSE 8085

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8085/health || exit 1

ENTRYPOINT ["uvicorn", "model_app.main:app", "--host", "0.0.0.0", "--port", "8085"]
