# Architecture Specification: Highly Available AI Microservices (HAMS)

## 1. System Overview

The **Highly Available AI Microservices (HAMS)** platform is a cloud-native, distributed backend architecture engineered to ingest, preprocess, store, and orchestrate high-throughput concurrent AI training data pipelines.

```
                           +----------------------------------------+
                           |           External Clients             |
                           +-------------------+--------------------+
                                               | (HTTPS / REST)
                                               v
+----------------------------------------------------------------------------------------------------+
|                                    API Gateway (FastAPI)                                           |
|       - Sliding Window Rate Limiting (120 req/min)        - JWT Auth & RBAC Token Validator        |
|       - Structured Correlation Request Logging             - Dynamic Round-Robin Service Discovery |
+--------+--------------------+---------------------+--------------------+-------------------+-------+
         |                    |                     |                    |                   |
 (HTTP)  |            (gRPC)  |             (gRPC)  |            (HTTP)  |           (HTTP)  |
         v                    v                     v                    v                   v
+-----------------+  +-----------------+  +------------------+  +-----------------+  +---------------+
| Storage Manager |  | Data Ingestion  |  |  Preprocessing   |  | Training Orch.  |  | Model Manager |
| (C++17 Engine)  |  | (C++17 / gRPC)  |  |  (C++17 / gRPC)  |  | (Python / async)|  | (Python/Fast) |
| - Sharding Ring |  | - Chunked Stream|  | - ML Transform   |  | - Priority Queue|  | - Semantic Ver|
| - Replication   |  | - Format Check  |  | - Feature Extr.  |  | - Load Balancer |  | - Deduplication|
| - Local & Cloud |  | - CRC32 & Magic |  | - Pipeline Stages|  | - DAG Execution |  | - Artifact Cas|
+--------+--------+  +--------+--------+  +--------+---------+  +--------+--------+  +-------+-------+
         |                    |                    |                     |                   |
         +--------------------+--------------------+---------------------+-------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
|                               50-Node Workload Rescheduler & Fault Engine                          |
|  - Phi Accrual Failure Detector (\(\Phi = -\log_{10} P_{later}\))                                   |
|  - 50 Heterogeneous Nodes (Standard Compute, High-Memory, GPU-Accelerated, Edge)                  |
|  - Real-Time Automated Workload Rescheduling with Priority Preemption                              |
|  - Cascading Failure Mitigation & Degraded Mode Fallbacks                                          |
+--------------------------------------------------+-------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
|                             Monitoring & Telemetry Subsystem                                       |
|  - Cluster-wide Heartbeat Monitor (5s TTL)            - Prometheus Metrics Exporter                |
|  - Multi-service Consecutive Failure Alerting         - Rolling Uptime & Latency Quantiles         |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Distributed C++ Core Microservices

### 2.1 Shared C++ Resilience Library (`hams_shared`)
- **`CircuitBreaker`**: Finite state machine with `CLOSED`, `OPEN`, and `HALF_OPEN` states. Features exponential backoff, configurable consecutive failure threshold (default 5), recovery timeout (default 15s), and probe rate limiting.
- **`HealthChecker`**: Embedded non-blocking HTTP health daemon (port 8081-8083) reporting ISO-8601 timestamps and component readiness.
- **`MetricsCollector`**: Thread-safe singleton providing Prometheus exposition format (text/plain; version=0.0.4) for Counters, Gauges, and Histograms with configurable bucket boundaries.
- **`RetryPolicy`**: Exponential backoff retry engine with Gaussian jitter distribution to prevent thundering herd problems.

### 2.2 Data Ingestion Service (`services/data-ingestion`)
- **Transport**: High-performance HTTP/2 gRPC streaming.
- **Protobuf**: `DataChunk` stream supporting streaming binary transfer with offset, checksum, and chunk ordering.
- **Validation Engine**:
  - `CSV`: Header validation, rectangular matrix column count enforcement.
  - `JSON`: AST validation supporting root array batches and single JSON payloads.
  - `PARQUET`: Header and footer magic byte verification (`PAR1`).
  - `BINARY`: Hardware-accelerated CRC-32 integrity validation.

### 2.3 Preprocessing Service (`services/preprocessing`)
- **Data Transforms**:
  - Min-Max scaling to arbitrary range bounds $[a, b]$.
  - Z-Score standardization ($\mu=0, \sigma=1$).
  - Missing value imputation: Mean, Median, Mode, and Constant strategies.
  - Outlier clipping / Winsorization based on empirical quantiles.
  - Set-based deduplication preserving order.
- **Feature Extraction**:
  - High-order moments: Mean, Variance, Skewness, Excess Kurtosis.
  - One-hot matrix encoding.
  - Murmur/FNV feature hashing trick for ultra-high dimensional sparse inputs.
  - Dimensionality reduction projection matrix.
- **Pipeline Executor**: Multi-stage state machine streaming real-time stage progress updates back to clients over gRPC server-side streaming.

### 2.4 Storage Manager & Sharding Ring (`services/storage-manager`)
- **Consistent Hashing**: FNV-1a hash ring with 100 virtual nodes per physical host to ensure minimal key relocation during cluster topology changes ($K/N$).
- **Replication Manager**: Multi-replica quorum replication factor ($N=3$, Quorum $W = \lfloor N/2 \rfloor + 1$).
- **Write-Ahead Log (WAL)**: Monotonically increasing sequence IDs for durability and crash recovery.

---

## 3. Workload Rescheduling Across 50-Node Distributed Environments

### 3.1 Heterogeneous 50-Node Cluster Topology
The cluster topology simulates 50 production compute nodes with heterogeneous hardware profiles:
1. **Standard Compute (30 nodes)**: 8 CPU cores, 32 GB RAM, 0 GPU.
2. **High-Memory (8 nodes)**: 16 CPU cores, 128 GB RAM, 0 GPU.
3. **GPU-Accelerated (8 nodes)**: 16 CPU cores, 64 GB RAM, 4 NVIDIA Tensor Core GPUs.
4. **Edge / Utility (4 nodes)**: 4 CPU cores, 16 GB RAM, 0 GPU.

### 3.2 Phi Accrual Failure Detector Algorithm
Rather than relying on binary up/down heartbeat timeouts, the cluster utilizes Hayashibara et al.'s **$\Phi$ Accrual Failure Detector**:
$$\Phi = -\log_{10}(P_{\text{later}}(t - t_{\text{last}}))$$
Where $P_{\text{later}}(t)$ is the probability that a heartbeat arrives more than $t$ time units after the previous one, computed from a sliding window of historical inter-arrival intervals using the normal distribution's complementary error function:
$$P_{\text{later}}(t) = \frac{1}{2} \text{erfc}\left(\frac{t - \mu}{\sigma \sqrt{2}}\right)$$

When $\Phi \ge 8.0$ (corresponding to $P_{\text{later}} \le 10^{-8}$):
1. The suspect node is automatically transitioned to `FAILED`.
2. All assigned active and pending workloads on that node are retrieved.
3. The automated rescheduling engine re-routes each orphaned workload to surviving nodes meeting resource and affinity constraints.
4. If $>20\%$ of nodes fail simultaneously, the system triggers **Degraded Mode Protection**, prioritizing critical high-priority training workloads.

---

## 4. Azure AKS Infrastructure & Security Topology

- **Azure Kubernetes Service (AKS 1.28)**: System node pool for cluster management and auto-scaling user node pools (2-10 instances) for AI pipelines.
- **Private Networking**: Azure CNI VNet with dedicated subnets for AKS pods, database backends, and private endpoints.
- **Zero-Trust Network Policies**: Ingress strictly gated to the API Gateway; east-west communication governed by Calico network policies.
- **Pod Disruption Budgets (PDB)**: Guarantee high availability during node drainage, upgrades, and platform patches.
