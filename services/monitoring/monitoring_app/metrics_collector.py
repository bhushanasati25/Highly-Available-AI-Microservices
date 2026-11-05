import time
from typing import Dict, List, Any
from prometheus_client import Counter, Gauge, Histogram

REQUEST_COUNT = Counter("hams_requests_total", "Total requests received across services", ["service"])
REQUEST_LATENCY = Histogram("hams_request_latency_seconds", "Request latency across microservices", ["service"])
ACTIVE_NODES = Gauge("hams_cluster_active_nodes", "Total active compute nodes in the cluster")
SYSTEM_THROUGHPUT = Gauge("hams_system_throughput_qps", "Current system query per second")

class SystemMetricsAggregator:
    def __init__(self):
        self._samples: List[Dict[str, Any]] = []

    def record_sample(self, service: str, latency: float, status_code: int):
        REQUEST_COUNT.labels(service=service).inc()
        REQUEST_LATENCY.labels(service=service).observe(latency)
        self._samples.append({
            "service": service,
            "latency": latency,
            "status": status_code,
            "timestamp": time.time()
        })
        if len(self._samples) > 1000:
            self._samples.pop(0)

    def get_summary(self) -> Dict[str, Any]:
        if not self._samples:
            return {"total_samples": 0, "avg_latency_ms": 0.0, "error_rate": 0.0}

        total = len(self._samples)
        errors = sum(1 for s in self._samples if s["status"] >= 500)
        avg_lat = sum(s["latency"] for s in self._samples) / total

        return {
            "total_samples": total,
            "avg_latency_ms": round(avg_lat * 1000, 2),
            "error_rate": round(errors / total, 4),
        }

metrics_aggregator = SystemMetricsAggregator()
