# High-Throughput AI Inference Latency & SLA Scorecard

- **Evaluated Model:** `transformer-llm-7b`
- **SLA Latency Target (p99):** `50.0 ms`
- **Peak Serving Throughput:** `42,689.3 inferences/sec` (Batch Size: `128`)
- **Compliance Status:** `PASSED (Compliant)`

### Benchmark Results

| Batch Size | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Throughput (inf/sec) | SLA Result |
|:---|:---|:---|:---|:---|:---|:---|
| 1 | 0.53 | 0.54 | 0.55 | 0.56 | 1,878.0 | ✅ PASS |
| 8 | 0.91 | 0.93 | 0.93 | 0.94 | 8,759.3 | ✅ PASS |
| 16 | 1.10 | 1.12 | 1.13 | 1.14 | 14,485.4 | ✅ PASS |
| 32 | 1.40 | 1.44 | 1.45 | 1.46 | 22,737.6 | ✅ PASS |
| 64 | 1.98 | 2.11 | 2.13 | 2.16 | 31,671.4 | ✅ PASS |
| 128 | 2.93 | 3.18 | 3.22 | 3.23 | 42,689.3 | ✅ PASS |
