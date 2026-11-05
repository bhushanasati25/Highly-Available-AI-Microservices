FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/python/ /app/shared/python/
COPY services/monitoring/requirements.txt /app/services/monitoring/requirements.txt

RUN pip install --no-cache-dir -r /app/services/monitoring/requirements.txt
RUN pip install --no-cache-dir -e /app/shared/python/

COPY services/monitoring/monitoring_app /app/services/monitoring/monitoring_app

WORKDIR /app/services/monitoring

EXPOSE 8086

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8086/health || exit 1

ENTRYPOINT ["uvicorn", "monitoring_app.main:app", "--host", "0.0.0.0", "--port", "8086"]
