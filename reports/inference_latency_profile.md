# High-Throughput AI Inference Latency & SLA Scorecard

- **Evaluated Model:** `transformer-llm-7b`
- **SLA Latency Target (p99):** `50.0 ms`
- **Peak Serving Throughput:** `58,867.3 inferences/sec` (Batch Size: `128`)
- **Compliance Status:** `PASSED (Compliant)`

### Benchmark Results

| Batch Size | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Throughput (inf/sec) | SLA Result |
|:---|:---|:---|:---|:---|:---|:---|
| 1 | 0.48 | 0.50 | 0.50 | 0.51 | 2,035.4 | ✅ PASS |
| 8 | 0.82 | 0.87 | 0.89 | 0.91 | 9,484.7 | ✅ PASS |
| 16 | 0.96 | 0.99 | 1.02 | 1.03 | 16,362.2 | ✅ PASS |
| 32 | 1.19 | 1.20 | 1.20 | 1.20 | 26,716.5 | ✅ PASS |
| 64 | 1.55 | 1.58 | 1.58 | 1.58 | 41,032.8 | ✅ PASS |
| 128 | 2.16 | 2.22 | 2.23 | 2.25 | 58,867.3 | ✅ PASS |
