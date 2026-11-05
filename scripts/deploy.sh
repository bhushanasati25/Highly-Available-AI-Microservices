#!/usr/bin/env bash
set -euo pipefail

ENV="${1:-dev}"
echo "=========================================================="
echo "HAMS: Deploying Highly Available Microservices to: $ENV"
echo "=========================================================="

NAMESPACE="hams-${ENV}"

echo "[*] Ensuring Kubernetes namespace $NAMESPACE exists..."
kubectl apply -f infra/k8s/namespace.yaml

echo "[*] Applying configuration and secrets..."
kubectl apply -n "$NAMESPACE" -f infra/k8s/configmaps/
kubectl apply -n "$NAMESPACE" -f infra/k8s/secrets.yaml

echo "[*] Applying network policies and pod disruption budgets..."
kubectl apply -n "$NAMESPACE" -f infra/k8s/network-policy.yaml
kubectl apply -n "$NAMESPACE" -f infra/k8s/pdb.yaml

echo "[*] Applying Kubernetes Services..."
kubectl apply -n "$NAMESPACE" -f infra/k8s/services/

echo "[*] Deploying Microservice Workloads..."
kubectl apply -n "$NAMESPACE" -f infra/k8s/deployments/

echo "[*] Applying Horizontal Pod Autoscalers..."
kubectl apply -n "$NAMESPACE" -f infra/k8s/hpa/

echo "[*] Waiting for deployment rollouts..."
kubectl rollout status deployment/api-gateway -n "$NAMESPACE" --timeout=120s
kubectl rollout status deployment/scheduler -n "$NAMESPACE" --timeout=120s

echo "=========================================================="
echo "[+] Deployment to $NAMESPACE completed successfully!"
echo "=========================================================="
