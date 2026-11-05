# API Reference: Highly Available AI Microservices

All public endpoints are exposed through the **API Gateway** on port `8080` (or directly per microservice internally).

---

## 1. Authentication

### Obtain Bearer Token
- **Endpoint**: `POST /api/v1/auth/token?username={username}`
- **Description**: Generates a cryptographically signed JWT token for API requests.
- **Response**:
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

---

## 2. Data Ingestion Service

### Submit Ingestion Job
- **Endpoint**: `POST /api/v1/ingest`
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
```json
{
  "source_id": "s3://ai-bucket/datasets/raw_features.csv",
  "format": "CSV",
  "metadata": {"source": "etl_pipeline", "version": "2.1"},
  "schema_id": "schema-v1",
  "data_payload": "id,feature_1,feature_2\n1,10.5,20.2\n2,11.0,21.5"
}
```
- **Response** `(202 Accepted)`:
```json
{
  "job_id": "job-a482b6c109df",
  "status": "PROCESSING",
  "records_processed": 2,
  "errors": []
}
```

### Query Ingestion Status
- **Endpoint**: `GET /api/v1/ingest/{job_id}`
- **Response** `(200 OK)`:
```json
{
  "job_id": "job-a482b6c109df",
  "status": "OK",
  "records_processed": 2,
  "errors": []
}
```

### Validate Ingestion Data
- **Endpoint**: `POST /api/v1/ingest/{job_id}/validate`
- **Response** `(200 OK)`:
```json
{
  "job_id": "job-a482b6c109df",
  "valid": true,
  "validation_errors": []
}
```

---

## 3. AI Training Orchestrator

### Submit Training Job
- **Endpoint**: `POST /api/v1/training/jobs`
- **Request Body**:
```json
{
  "model_type": "transformer-llm-7b",
  "dataset_id": "ds-corpus-clean-v2",
  "hyperparameters": {
    "learning_rate": 0.0002,
    "batch_size": 32,
    "warmup_steps": 500
  },
  "priority": 8,
  "required_gpu": 2,
  "required_cpu": 8.0,
  "required_memory_gb": 32.0
}
```
- **Response** `(202 Accepted)`:
```json
{
  "job_id": "train-39df94821a00",
  "model_type": "transformer-llm-7b",
  "dataset_id": "ds-corpus-clean-v2",
  "priority": 8,
  "status": "QUEUED",
  "progress": 0.0,
  "assigned_node": null,
  "metrics": {},
  "retries": 0
}
```

### List / Query Training Jobs
- **Endpoint**: `GET /api/v1/training/jobs`
- **Query Params**: `status_filter=RUNNING`
- **Endpoint**: `GET /api/v1/training/jobs/{job_id}`

### Cancel Training Job
- **Endpoint**: `DELETE /api/v1/training/jobs/{job_id}`

---

## 4. Model Registry & Version Manager

### Register Model
- **Endpoint**: `POST /api/v1/models`
- **Request Body**:
```json
{
  "name": "bert-finetuned-ner",
  "framework": "pytorch",
  "description": "Named Entity Recognition model fine-tuned on clinical notes",
  "tags": {"domain": "healthcare", "tier": "production"}
}
```
- **Response** `(201 Created)`:
```json
{
  "id": "mod-8f203819aa",
  "name": "bert-finetuned-ner",
  "framework": "pytorch",
  "description": "Named Entity Recognition model fine-tuned on clinical notes",
  "tags": {"domain": "healthcare", "tier": "production"},
  "latest_version": "v1.0.0",
  "created_at": 1700000000.0
}
```

### Deploy / Promote Model Version
- **Endpoint**: `POST /api/v1/models/{model_id}/deploy`
- **Request Body**:
```json
{
  "version": "v1.0.0",
  "target_environment": "production"
}
```
- **Response** `(200 OK)`:
```json
{
  "model_id": "mod-8f203819aa",
  "version": "v1.0.0",
  "stage": "production",
  "status": "DEPLOYED",
  "artifact_url": "https://azure-blob.hams.ai/models/sha256...?sig=..."
}
```

---

## 5. Workload Rescheduler & 50-Node Cluster API

### Submit Workload to Cluster
- **Endpoint**: `POST /api/v1/workloads`
- **Request Body**:
```json
{
  "name": "pretraining-epoch-1",
  "required_cpu": 8.0,
  "required_memory": 32.0,
  "required_gpu": 2,
  "required_disk": 100.0,
  "priority": 9,
  "algorithm": "LEAST_LOADED"
}
```

### Cluster Telemetry & Capacity
- **Endpoint**: `GET /api/v1/cluster/status`
- **Response** `(200 OK)`:
```json
{
  "node_count": 50,
  "active_nodes": 50,
  "failed_nodes": 0,
  "draining_nodes": 0,
  "cluster_health": "HEALTHY",
  "total_cpu": 560.0,
  "available_cpu": 520.0,
  "cpu_utilization_pct": 7.1,
  "total_memory_gb": 2496.0,
  "available_memory_gb": 2368.0,
  "memory_utilization_pct": 5.1,
  "total_gpu": 32,
  "available_gpu": 30,
  "total_scheduled_workloads": 12,
  "total_rescheduled_workloads": 0
}
```

### Hardware Failure Simulation & Auto-Rescheduling Injection
- **Endpoint**: `POST /api/v1/simulate/failure`
- **Request Body**:
```json
{
  "node_id": "node-005"
}
```
- **Response**:
```json
{
  "failed_node": "node-005",
  "orphaned_count": 3,
  "rescheduled_count": 3,
  "rescheduled_ids": ["wkl-01a", "wkl-02b", "wkl-03c"]
}
```

### Recover Node
- **Endpoint**: `POST /api/v1/simulate/recovery/{node_id}`
- **Response**: `{"status": "RECOVERED", "node_id": "node-005"}`

---

## 6. System Health & Prometheus Metrics

- **System Aggregated Health**: `GET /api/v1/system/health`
- **Individual Health**: `GET /health` and `GET /ready` on all microservices
- **Prometheus Metrics**: `GET /metrics` on all microservices
