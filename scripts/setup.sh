#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "HAMS: Highly Available AI Microservices Environment Setup"
echo "=========================================================="

# Check tool prerequisites
for cmd in docker cmake python3 git; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "[-] Error: required command '$cmd' is not installed."
        exit 1
    fi
    echo "[+] Found prerequisite: $cmd"
done

# Python virtual environment
echo "[*] Initializing Python virtual environment..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[*] Upgrading pip and installing Python dependencies..."
pip install --upgrade pip
pip install -e shared/python/
pip install -r services/api-gateway/requirements.txt
pip install -r services/training-orchestrator/requirements.txt
pip install -r services/model-manager/requirements.txt
pip install -r services/monitoring/requirements.txt
pip install -r scheduler/requirements.txt

echo "[*] Building local Docker container images..."
docker compose build --parallel

echo "=========================================================="
echo "[+] Setup completed successfully!"
echo "Run 'docker compose up -d' or 'make up' to launch cluster."
echo "=========================================================="
