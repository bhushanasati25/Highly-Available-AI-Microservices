FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/python/ /app/shared/python/
COPY services/api-gateway/requirements.txt /app/services/api-gateway/requirements.txt

RUN pip install --no-cache-dir -r /app/services/api-gateway/requirements.txt
RUN pip install --no-cache-dir -e /app/shared/python/

COPY services/api-gateway/gateway_app /app/services/api-gateway/gateway_app

WORKDIR /app/services/api-gateway

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["uvicorn", "gateway_app.main:app", "--host", "0.0.0.0", "--port", "8080"]
