#!/usr/bin/env bash
set -euo pipefail

BASE_HOST="${1:-localhost}"

echo "=========================================================="
echo "HAMS: Microservices Cluster Health Inspection"
echo "Target Host: $BASE_HOST"
echo "=========================================================="

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

ALL_HEALTHY=true

for entry in "${SERVICES[@]}"; do
    NAME="${entry%%:*}"
    URL="${entry#*:}"

    printf "%-25s ... " "$NAME"
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
    echo -e "\033[33m[!] Warning: One or more services are not ready.\033[0m"
    exit 1
fi
