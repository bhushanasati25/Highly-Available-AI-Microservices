# Deployment & Operations Guide: Highly Available AI Microservices

## 1. Local Development Deployment

### Prerequisites
- Docker Engine 24.0+ & Docker Compose v2+
- Python 3.11+
- CMake 3.16+ (for compiling C++ microservices natively)
- `curl`, `jq`, `make`

### Quick Start
```bash
# Clone and enter directory
cd "Highly Available AI Microservices"

# Run automated setup
./scripts/setup.sh

# Start full multi-service cluster
make up
# or: docker compose up -d
```

### Validating Cluster Health
Run the automated health checker script:
```bash
./scripts/health-check.sh localhost
```
Expected output:
```text
==========================================================
HAMS: Microservices Cluster Health Inspection
Target Host: localhost
==========================================================
API Gateway               ... [HEALTHY 200 OK]
Data Ingestion            ... [HEALTHY 200 OK]
Preprocessing             ... [HEALTHY 200 OK]
Storage Manager           ... [HEALTHY 200 OK]
Training Orchestrator     ... [HEALTHY 200 OK]
Model Manager             ... [HEALTHY 200 OK]
Monitoring Telemetry      ... [HEALTHY 200 OK]
Workload Scheduler        ... [HEALTHY 200 OK]
==========================================================
[+] All microservices are healthy and operating normally.
```

---

## 2. Cloud Deployment (Microsoft Azure AKS)

### Step 1: Provision Cloud Infrastructure with Terraform
```bash
cd infra/terraform

# Initialize Terraform modules
terraform init

# Plan with production variables
terraform plan -var-file=environments/prod.tfvars -out=tfplan

# Apply infrastructure (Provisions VNet, NSGs, ACR, AKS, Log Analytics)
terraform apply tfplan
```

### Step 2: Configure `kubectl` Credentials
```bash
az aks get-credentials \
  --resource-group hams-prod-rg \
  --name hams-prod-aks \
  --overwrite-existing
```

### Step 3: Deploy Microservices via Automated Script
```bash
# From project root
./scripts/deploy.sh prod
```

The script automatically executes:
1. Namespace configuration (`hams-prod`).
2. ConfigMap and Secret deployment.
3. Network policy and PodDisruptionBudget application.
4. Core services and deployment manifest rollout.
5. Horizontal Pod Autoscaler binding (min 3, max 15 pods for API Gateway).
6. Rollout verification and readiness probe gate validation.

---

## 3. High Availability & Failure Rescheduling Verification

To verify the automated failure mitigation across the 50-node environment:

1. **Submit concurrent AI training workloads:**
```bash
curl -X POST http://localhost:8087/api/v1/workloads \
  -H "Content-Type: application/json" \
  -d '{
    "name": "resilience-verification-task",
    "required_cpu": 4.0,
    "required_memory": 16.0,
    "required_gpu": 1,
    "priority": 8
  }'
```
Take note of the `assigned_node` (e.g. `node-008`).

2. **Inject a simulated hardware failure:**
```bash
curl -X POST http://localhost:8087/api/v1/simulate/failure \
  -H "Content-Type: application/json" \
  -d '{"node_id": "node-008"}'
```

3. **Verify real-time automatic rescheduling:**
The response immediately details:
```json
{
  "failed_node": "node-008",
  "orphaned_count": 1,
  "rescheduled_count": 1,
  "rescheduled_ids": ["wkl-..."]
}
```
Querying the workload via `GET /api/v1/workloads/{workload_id}` will show that its `assigned_node` has migrated to a healthy node and its `reschedule_history` records the transition without pipeline disruption.

---

## 4. Runbooks & Troubleshooting

### Issue: Service Reports Degraded
1. Check monitoring alerts: `GET http://localhost:8086/alerts`
2. Inspect service container logs:
```bash
docker compose logs -f data-ingestion
# or in K8s:
kubectl logs -n hams-prod deployment/data-ingestion --tail=100
```

### Issue: Rate Limit Tripping (HTTP 429)
The API Gateway enforces a sliding-window rate limit (default 120 req/min). To adjust, configure `HAMS_RATE_LIMIT_PER_MINUTE` in `infra/k8s/configmaps/app-config.yaml` and re-apply.
