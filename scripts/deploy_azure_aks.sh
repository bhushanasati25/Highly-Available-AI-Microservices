#!/usr/bin/env bash
# ==============================================================================
# Highly Available AI Microservices — Turnkey Azure AKS Deployer
# Provisions Azure Infrastructure (AKS, ACR, VNet), builds images, and deploys
# microservices using Helm and Terraform.
# ==============================================================================
set -euo pipefail

# ANSI formatting
BOLD="\033[1m"
GREEN="\033[92m"
YELLOW="\033[93m"
CYAN="\033[96m"
RED="\033[91m"
RESET="\033[0m"

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-hams-prod-rg}"
LOCATION="${AZURE_LOCATION:-eastus}"
CLUSTER_NAME="${AZURE_AKS_CLUSTER:-hams-aks-cluster}"
ACR_NAME="${AZURE_ACR_NAME:-hamsregistry$RANDOM}"
ENVIRONMENT="${DEPLOY_ENV:-production}"

echo -e "${BOLD}${CYAN}================================================================${RESET}"
echo -e "${BOLD}${CYAN}HAMS: Turnkey Azure Kubernetes Service (AKS) Deployment Engine  ${RESET}"
echo -e "${BOLD}${CYAN}================================================================${RESET}"
echo -e "Resource Group : ${BOLD}${RESOURCE_GROUP}${RESET}"
echo -e "Location       : ${BOLD}${LOCATION}${RESET}"
echo -e "AKS Cluster    : ${BOLD}${CLUSTER_NAME}${RESET}"
echo -e "Environment    : ${BOLD}${ENVIRONMENT}${RESET}\n"

# 1. Prerequisite Validation
echo -e "${BOLD}[Step 1/6] Validating local toolchains...${RESET}"
for tool in az kubectl helm terraform docker; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo -e "${RED}[!] Error: Required tool '${tool}' is not installed or not on PATH.${RESET}"
        exit 1
    fi
    echo -e "  ${GREEN}✓${RESET} $tool found ($(command -v $tool))"
done

# 2. Azure CLI Authentication Check
echo -e "\n${BOLD}[Step 2/6] Verifying Azure CLI authentication...${RESET}"
if ! az account show >/dev/null 2>&1; then
    echo -e "${YELLOW}[!] Not logged into Azure CLI. Initiating login...${RESET}"
    az login
fi
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
echo -e "  ${GREEN}✓${RESET} Authenticated to Azure Subscription: ${BOLD}${SUBSCRIPTION_NAME}${RESET}"

# 3. Provision Infrastructure via Terraform
echo -e "\n${BOLD}[Step 3/6] Applying Terraform Infrastructure as Code...${RESET}"
pushd infra/terraform >/dev/null
terraform init
terraform apply -auto-approve \
    -var="resource_group_name=${RESOURCE_GROUP}" \
    -var="location=${LOCATION}" \
    -var="cluster_name=${CLUSTER_NAME}" \
    -var="environment=${ENVIRONMENT}"
popd >/dev/null
echo -e "  ${GREEN}✓${RESET} Azure AKS Cluster and ACR successfully provisioned!"

# 4. Get AKS Credentials
echo -e "\n${BOLD}[Step 4/6] Connecting kubectl to Azure AKS...${RESET}"
az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$CLUSTER_NAME" --overwrite-existing
kubectl cluster-info

# 5. Deploy Helm Chart
echo -e "\n${BOLD}[Step 5/6] Deploying Microservices Stack via Helm...${RESET}"
helm upgrade --install hams infra/helm/hams \
    --namespace hams-system \
    --create-namespace \
    --set global.environment="${ENVIRONMENT}" \
    --set apiGateway.replicaCount=3 \
    --set trainingOrchestrator.replicaCount=2 \
    --set scheduler.replicaCount=2 \
    --wait --timeout 10m

# 6. Verify Rollouts
echo -e "\n${BOLD}[Step 6/6] Verifying High-Availability Deployment Rollouts...${RESET}"
kubectl rollout status deployment/api-gateway -n hams-system --timeout=120s
kubectl rollout status deployment/training-orchestrator -n hams-system --timeout=120s
kubectl rollout status deployment/scheduler -n hams-system --timeout=120s

echo -e "\n${BOLD}${GREEN}================================================================${RESET}"
echo -e "${BOLD}${GREEN}[✓] HAMS Cloud Deployment Complete on Azure AKS!               ${RESET}"
echo -e "${BOLD}${GREEN}================================================================${RESET}"
kubectl get services -n hams-system
