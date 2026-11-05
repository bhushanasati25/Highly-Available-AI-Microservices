from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

try:
    from .node_manager import NodeManager, NodeStatus
    from .scheduler import WorkloadScheduler, SchedulingAlgorithm, WorkloadStatus
    from .failure_detector import FailureDetector
except ImportError:
    from node_manager import NodeManager, NodeStatus
    from scheduler import WorkloadScheduler, SchedulingAlgorithm, WorkloadStatus
    from failure_detector import FailureDetector

router = APIRouter(prefix="/api/v1", tags=["Workload Rescheduler & Cluster Management"])

# Global singletons initialized during lifespan in main.py
node_mgr = NodeManager(node_count=50)
workload_sched = WorkloadScheduler(node_mgr)
fail_detector = FailureDetector(node_mgr, workload_sched)

class WorkloadSubmitRequest(BaseModel):
    name: str = Field(..., example="distributed-transformer-fine-tuning")
    required_cpu: float = Field(4.0, ge=0.5)
    required_memory: float = Field(16.0, ge=1.0)
    required_gpu: int = Field(0, ge=0)
    required_disk: float = Field(20.0, ge=0.0)
    priority: int = Field(5, ge=1, le=10)
    affinity: Optional[Dict[str, str]] = None
    anti_affinity: Optional[Dict[str, str]] = None
    algorithm: Optional[SchedulingAlgorithm] = None

class SimulateFailureRequest(BaseModel):
    node_id: str = Field(..., example="node-005")

@router.post("/workloads", status_code=status.HTTP_201_CREATED)
async def submit_workload(req: WorkloadSubmitRequest):
    wkl = await workload_sched.schedule(
        name=req.name,
        required_cpu=req.required_cpu,
        required_memory=req.required_memory,
        required_gpu=req.required_gpu,
        required_disk=req.required_disk,
        priority=req.priority,
        affinity=req.affinity,
        anti_affinity=req.anti_affinity,
        algorithm=req.algorithm
    )
    return wkl.to_dict()

@router.get("/workloads")
async def list_workloads(status_filter: Optional[WorkloadStatus] = None, node_id: Optional[str] = None):
    res = []
    for w in workload_sched.workloads.values():
        if status_filter and w.status != status_filter:
            continue
        if node_id and w.assigned_node != node_id:
            continue
        res.append(w.to_dict())
    return res

@router.get("/workloads/{workload_id}")
async def get_workload(workload_id: str):
    if workload_id not in workload_sched.workloads:
        raise HTTPException(status_code=404, detail="Workload not found")
    return workload_sched.workloads[workload_id].to_dict()

@router.post("/workloads/{workload_id}/reschedule")
async def manual_reschedule(workload_id: str):
    success = await workload_sched.reschedule(workload_id, reason="manual_operator_request")
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reschedule workload (no matching capacity)")
    return workload_sched.workloads[workload_id].to_dict()

@router.delete("/workloads/{workload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_workload(workload_id: str):
    success = await workload_sched.deschedule(workload_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workload not found")
    return None

@router.get("/cluster/status")
async def cluster_status():
    nodes = list(node_mgr.nodes.values())
    active_count = sum(1 for n in nodes if n.status == NodeStatus.ACTIVE)
    failed_count = sum(1 for n in nodes if n.status == NodeStatus.FAILED)
    draining_count = sum(1 for n in nodes if n.status == NodeStatus.DRAINING)

    total_cpu = sum(n.total_cpu for n in nodes)
    avail_cpu = sum(n.available_cpu for n in nodes)
    total_mem = sum(n.total_memory for n in nodes)
    avail_mem = sum(n.available_memory for n in nodes)
    total_gpu = sum(n.total_gpu for n in nodes)
    avail_gpu = sum(n.available_gpu for n in nodes)

    return {
        "node_count": len(nodes),
        "active_nodes": active_count,
        "failed_nodes": failed_count,
        "draining_nodes": draining_count,
        "cluster_health": "HEALTHY" if failed_count == 0 else ("DEGRADED" if fail_detector.degraded_mode else "WARNING"),
        "total_cpu": total_cpu,
        "available_cpu": round(avail_cpu, 2),
        "cpu_utilization_pct": round(((total_cpu - avail_cpu) / total_cpu * 100) if total_cpu else 0, 1),
        "total_memory_gb": total_mem,
        "available_memory_gb": round(avail_mem, 2),
        "memory_utilization_pct": round(((total_mem - avail_mem) / total_mem * 100) if total_mem else 0, 1),
        "total_gpu": total_gpu,
        "available_gpu": avail_gpu,
        "total_scheduled_workloads": workload_sched.total_scheduled_count,
        "total_rescheduled_workloads": workload_sched.total_rescheduled_count,
    }

@router.get("/cluster/nodes")
async def list_cluster_nodes():
    return [n.to_dict() for n in node_mgr.nodes.values()]

@router.get("/cluster/nodes/{node_id}")
async def get_node_details(node_id: str):
    if node_id not in node_mgr.nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    return node_mgr.nodes[node_id].to_dict()

@router.post("/cluster/nodes/{node_id}/drain")
async def drain_cluster_node(node_id: str):
    if node_id not in node_mgr.nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    orphaned = await node_mgr.drain_node(node_id)
    rescheduled = []
    for w_id in orphaned:
        ok = await workload_sched.reschedule(w_id, reason="node_draining")
        if ok:
            rescheduled.append(w_id)
    return {"node_id": node_id, "drained_workloads": len(orphaned), "rescheduled": rescheduled}

@router.post("/cluster/nodes/{node_id}/maintenance")
async def maintenance_cluster_node(node_id: str):
    if node_id not in node_mgr.nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    orphaned = await node_mgr.set_maintenance(node_id)
    for w_id in orphaned:
        await workload_sched.reschedule(w_id, reason="node_maintenance")
    return {"node_id": node_id, "status": "MAINTENANCE", "migrated": len(orphaned)}

@router.post("/cluster/nodes/{node_id}/activate")
async def activate_cluster_node(node_id: str):
    if node_id not in node_mgr.nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    await node_mgr.activate_node(node_id)
    fail_detector.record_heartbeat(node_id)
    return {"node_id": node_id, "status": "ACTIVE"}

@router.post("/simulate/failure")
async def simulate_hardware_failure(req: SimulateFailureRequest):
    if req.node_id not in node_mgr.nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    res = await fail_detector.simulate_node_failure(req.node_id)
    return res

@router.post("/simulate/recovery/{node_id}")
async def simulate_hardware_recovery(node_id: str):
    if node_id not in node_mgr.nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    await fail_detector.simulate_node_recovery(node_id)
    return {"status": "RECOVERED", "node_id": node_id}

@router.get("/metrics")
async def get_scheduler_metrics():
    return {
        "scheduled_count": workload_sched.total_scheduled_count,
        "rescheduled_count": workload_sched.total_rescheduled_count,
        "failure_events_count": len(fail_detector.failure_events),
        "degraded_mode": fail_detector.degraded_mode,
    }

@router.get("/history")
async def get_failure_history():
    return fail_detector.failure_events[-30:]
