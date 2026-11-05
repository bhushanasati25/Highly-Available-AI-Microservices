FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/python/ /app/shared/python/
COPY scheduler/requirements.txt /app/scheduler/requirements.txt

RUN pip install --no-cache-dir -r /app/scheduler/requirements.txt
RUN pip install --no-cache-dir -e /app/shared/python/

COPY scheduler/scheduler_app /app/scheduler/scheduler_app

WORKDIR /app/scheduler

EXPOSE 8087

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8087/health || exit 1

ENTRYPOINT ["uvicorn", "scheduler_app.main:app", "--host", "0.0.0.0", "--port", "8087"]
