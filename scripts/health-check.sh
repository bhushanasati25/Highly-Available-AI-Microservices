#!/usr/bin/env bash
set -euo pipefail

BASE_HOST="localhost"
CHECK_PROBES=false

for arg in "$@"; do
    if [ "$arg" = "--probes" ]; then
        CHECK_PROBES=true
    elif [[ "$arg" != -* ]]; then
        BASE_HOST="$arg"
    fi
done

echo "=========================================================="
echo "HAMS: Microservices Cluster Health Inspection"
echo "Target Host: $BASE_HOST"
if [ "$CHECK_PROBES" = true ]; then
    echo "Mode: Cloud-Native 3-Tier Kubernetes Probes Inspection"
fi
echo "=========================================================="

if [ "$CHECK_PROBES" = true ]; then
    PROBES=(
        "API Gateway (Liveness /healthz):http://${BASE_HOST}:8080/healthz"
        "API Gateway (Readiness /readyz):http://${BASE_HOST}:8080/readyz"
        "API Gateway (Startup /startupz):http://${BASE_HOST}:8080/startupz"
        "Data Ingestion (/healthz):http://${BASE_HOST}:8081/healthz"
        "Preprocessing (/healthz):http://${BASE_HOST}:8082/healthz"
        "Storage Manager (/healthz):http://${BASE_HOST}:8083/healthz"
        "Training Orchestrator (/healthz):http://${BASE_HOST}:8084/healthz"
        "Model Manager (/healthz):http://${BASE_HOST}:8085/healthz"
        "Monitoring Telemetry (/healthz):http://${BASE_HOST}:8086/healthz"
        "Workload Scheduler (/healthz):http://${BASE_HOST}:8087/healthz"
    )
    TARGET_LIST=("${PROBES[@]}")
else
    SERVICES=(
        "API Gateway:http://${BASE_HOST}:8080/health"
        "Data Ingestion:http://${BASE_HOST}:8081/health"
        "Preprocessing:http://${BASE_HOST}:8082/health"
        "Storage Manager:http://${BASE_HOST}:8083/health"
        "Training Orchestrator:http://${BASE_HOST}:8084/health"
        "Model Manager:http://${BASE_HOST}:8085/health"
        "Monitoring Telemetry:http://${BASE_HOST}:8086/health"
        "Workload Scheduler:http://${BASE_HOST}:8087/health"
    )
    TARGET_LIST=("${SERVICES[@]}")
fi

ALL_HEALTHY=true

for entry in "${TARGET_LIST[@]}"; do
    NAME="${entry%%:http*}"
    URL="http${entry#*:http}"

    printf "%-35s ... " "$NAME"
    if curl -s -f -m 3 "$URL" > /dev/null 2>&1; then
        echo -e "\033[32m[HEALTHY 200 OK]\033[0m"
    else
        echo -e "\033[31m[UNREACHABLE / DEGRADED]\033[0m"
        ALL_HEALTHY=false
    fi
done

echo "=========================================================="
if [ "$ALL_HEALTHY" = true ]; then
    echo -e "\033[32m[+] All microservices are healthy and operating normally.\033[0m"
    exit 0
else
    echo -e "\033[33m[!] Warning: One or more services are not reachable on host ${BASE_HOST}.\033[0m"
    exit 1
fi
