from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
try:
    from .heartbeat import HeartbeatMonitor
    from .health_checker import ServiceHealthMonitor
    from .metrics_collector import metrics_aggregator, ACTIVE_NODES
    from .drift_detector import drift_detector_instance
except ImportError:
    from heartbeat import HeartbeatMonitor
    from health_checker import ServiceHealthMonitor
    from metrics_collector import metrics_aggregator, ACTIVE_NODES
    from drift_detector import drift_detector_instance

router = APIRouter(tags=["Monitoring & Telemetry"])

heartbeat_monitor = HeartbeatMonitor(timeout_seconds=5.0)
service_health = ServiceHealthMonitor()

class HeartbeatPayload(BaseModel):
    cpu_usage: float = Field(0.0, ge=0.0, le=100.0)
    memory_usage: float = Field(0.0, ge=0.0, le=100.0)
    gpu_available: int = Field(0, ge=0)

class DriftAnalysisRequest(BaseModel):
    feature_name: str = Field(..., examples=["embedding_norm"])
    baseline: List[float] = Field(..., examples=[[1.0, 1.2, 1.5, 1.8, 2.0]])
    current: List[float] = Field(..., examples=[[3.0, 3.5, 4.0, 4.5, 5.0]])

@router.get("/status")
async def cluster_status():
    dead = heartbeat_monitor.scan_dead_nodes()
    nodes = heartbeat_monitor.get_node_statuses()
    services = service_health.get_service_statuses()
    ACTIVE_NODES.set(sum(1 for n in nodes if n["alive"]))

    return {
        "status": "HEALTHY" if not dead else "DEGRADED",
        "active_nodes_count": sum(1 for n in nodes if n["alive"]),
        "total_nodes_count": len(nodes),
        "recent_dead_nodes": dead,
        "services": services
    }

@router.get("/services")
async def get_services():
    return service_health.get_service_statuses()

@router.get("/nodes")
async def get_nodes():
    return heartbeat_monitor.get_node_statuses()

@router.post("/nodes/{node_id}/heartbeat")
async def send_heartbeat(node_id: str, payload: HeartbeatPayload):
    heartbeat_monitor.record_heartbeat(
        node_id=node_id,
        cpu=payload.cpu_usage,
        mem=payload.memory_usage,
        gpu=payload.gpu_available
    )
    return {"status": "ACK", "node_id": node_id}

@router.get("/alerts")
async def get_alerts():
    return service_health.alerts[-20:]

@router.get("/summary")
async def get_metrics_summary():
    return metrics_aggregator.get_summary()

@router.post("/drift")
async def check_data_drift(req: DriftAnalysisRequest):
    report = drift_detector_instance.analyze_feature_drift(
        feature_name=req.feature_name,
        baseline=req.baseline,
        current=req.current
    )
    return {
        "feature_name": report.feature_name,
        "psi_score": report.psi_score,
        "ks_statistic": report.ks_statistic,
        "drift_detected": report.drift_detected,
        "drift_severity": report.drift_severity,
        "baseline_sample_count": report.baseline_sample_count,
        "current_sample_count": report.current_sample_count,
        "details": report.details,
    }
