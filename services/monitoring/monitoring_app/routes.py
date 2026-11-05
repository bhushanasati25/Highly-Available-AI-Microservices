from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
try:
    from .heartbeat import HeartbeatMonitor
    from .health_checker import ServiceHealthMonitor
    from .metrics_collector import metrics_aggregator, ACTIVE_NODES
except ImportError:
    from heartbeat import HeartbeatMonitor
    from health_checker import ServiceHealthMonitor
    from metrics_collector import metrics_aggregator, ACTIVE_NODES

router = APIRouter(tags=["Monitoring & Telemetry"])

heartbeat_monitor = HeartbeatMonitor(timeout_seconds=5.0)
service_health = ServiceHealthMonitor()

class HeartbeatPayload(BaseModel):
    cpu_usage: float = Field(0.0, ge=0.0, le=100.0)
    memory_usage: float = Field(0.0, ge=0.0, le=100.0)
    gpu_available: int = Field(0, ge=0)

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
