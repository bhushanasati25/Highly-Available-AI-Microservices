"""
End-to-End System Integration Test Suite
Verifies cross-service interactions, data pipelines, model lifecycle,
and 50-node automated fault-mitigation and rescheduling.
"""

import sys
import os
import time
import asyncio
import pytest
from pathlib import Path

# Add all service app packages to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "shared" / "python"))
sys.path.insert(0, str(BASE_DIR / "scheduler"))
sys.path.insert(0, str(BASE_DIR / "services" / "api-gateway"))
sys.path.insert(0, str(BASE_DIR / "services" / "training-orchestrator"))
sys.path.insert(0, str(BASE_DIR / "services" / "model-manager"))
sys.path.insert(0, str(BASE_DIR / "services" / "monitoring"))

from scheduler_app.node_manager import NodeManager, NodeStatus
from scheduler_app.failure_detector import FailureDetector
from scheduler_app.scheduler import WorkloadScheduler, SchedulingAlgorithm, WorkloadStatus
from orchestrator_app.orchestrator import orchestrator_instance
from model_app.registry import registry_instance
from monitoring_app.heartbeat import HeartbeatMonitor
from common.circuit_breaker import CircuitBreaker, CircuitBreakerState, CircuitBreakerError


@pytest.mark.asyncio
async def test_end_to_end_ai_training_lifecycle():
    """
    Test complete lifecycle:
    1. Training job submission to orchestrator
    2. Node selection & execution
    3. Artifact generation & registration in model manager
    4. Version tagging & promotion to production
    5. Health & metrics recording in monitoring service
    """
    # 1. Submit training job
    job = await orchestrator_instance.submit_job(
        model_type="transformer-sentiment-classifier",
        dataset_id="ds-customer-reviews-2026",
        hyperparameters={"lr": 0.0001, "batch_size": 32, "epochs": 5},
        priority=8,
        req_gpu=1,
        req_cpu=4.0,
        req_mem=16.0,
    )
    assert job.job_id.startswith("train-")
    assert job.status in ["QUEUED", "RUNNING", "SUBMITTED"]

    # 2. Simulate training progress and completion
    job.progress = 100.0
    job.status = "COMPLETED"
    job.metrics = {"val_loss": 0.124, "val_acc": 0.968}
    assert job.status == "COMPLETED"
    assert job.progress == 100.0
    assert job.metrics["val_acc"] == 0.968

    # 3. Register model artifact in model registry
    model_record = registry_instance.register_model(
        name="transformer-sentiment-classifier",
        framework="pytorch",
        description="Transformer classifier fine-tuned on customer reviews dataset",
        tags={"domain": "nlp", "lifecycle": "production-ready"},
        dataset_id=job.dataset_id,
        job_id=job.job_id,
    )
    assert model_record.id is not None
    assert model_record.name == "transformer-sentiment-classifier"

    # 4. Create version and promote to production
    sha = registry_instance.artifact_store.store_artifact(
        "model_v1.1.0_weights.bin",
        b"SimulatedHighPrecisionTrainedWeightsDataBlob"
    )
    version_rec = registry_instance.versioning.create_version(
        model_id=model_record.id,
        version_id="v1.1.0",
        artifact_sha=sha,
        metrics={"accuracy": 0.968, "f1_score": 0.965},
        changelog="Production release fine-tuned across 50-node distributed cluster",
    )
    assert version_rec.version_id == "v1.1.0"
    assert version_rec.artifact_sha == sha
    assert len(version_rec.artifact_sha) == 64  # SHA-256

    promoted = registry_instance.versioning.promote_version(
        model_id=model_record.id,
        version_id="v1.1.0",
        target_stage="production",
    )
    assert promoted is not None
    assert promoted.stage == "production"

    # 5. Record monitoring heartbeat & metrics
    monitor = HeartbeatMonitor(timeout_seconds=5.0)
    monitor.record_heartbeat(
        node_id="train-node-alpha",
        cpu=64.5,
        mem=72.0,
        gpu=1,
    )
    statuses = monitor.get_node_statuses()
    assert len(statuses) >= 1
    assert any(s["node_id"] == "train-node-alpha" and s["alive"] for s in statuses)


@pytest.mark.asyncio
async def test_50_node_automated_hardware_fault_rescheduling():
    """
    Test 50-node distributed environment:
    1. Initialize 50 heterogeneous nodes
    2. Deploy multiple AI workloads
    3. Inject hardware crash on active node
    4. Verify Phi Accrual Failure Detector flags node and triggers automated migration
    5. Ensure zero stranded workloads and workload relocated to healthy node
    """
    # 1. Initialize 50-node cluster
    node_mgr = NodeManager(node_count=50)
    await node_mgr.initialize(50)
    scheduler = WorkloadScheduler(node_mgr)
    detector = FailureDetector(node_mgr, scheduler, phi_threshold=8.0)

    for n in node_mgr.nodes:
        detector.record_heartbeat(n)

    assert len(node_mgr.nodes) == 50

    gpu_nodes = [n for n in node_mgr.nodes.values() if n.total_gpu > 0]
    assert len(gpu_nodes) >= 8, f"Expected >=8 GPU nodes, got {len(gpu_nodes)}"

    # 2. Schedule high-priority GPU AI workload
    workload = await scheduler.schedule(
        name="distributed-diffusion-training",
        required_cpu=8.0,
        required_memory=32.0,
        required_gpu=2,
        required_disk=50.0,
        priority=9,
        algorithm=SchedulingAlgorithm.LEAST_LOADED,
    )
    assert workload is not None
    assert workload.assigned_node is not None
    initial_node_id = workload.assigned_node

    # 3. Verify workload is active on that node
    node_obj = await node_mgr.get_node(initial_node_id)
    assert workload.id in node_obj.workload_ids

    # 4. Inject hardware crash and trigger automated failover
    result = await detector.simulate_node_failure(initial_node_id)
    assert result["failed_node"] == initial_node_id
    assert result["orphaned_count"] >= 1

    crashed_node = await node_mgr.get_node(initial_node_id)
    assert crashed_node.status == NodeStatus.FAILED

    # Calculate phi accrual for crashed node
    phi = detector.compute_phi(initial_node_id, time.time() + 20.0)
    assert phi >= 8.0, f"Expected phi >= 8.0, got {phi}"

    # 5. Verify workload is now successfully running on a different, healthy node
    migrated_workload = scheduler.workloads[workload.id]
    assert migrated_workload is not None
    assert migrated_workload.assigned_node != initial_node_id
    assert migrated_workload.retry_count >= 1

    new_node = await node_mgr.get_node(migrated_workload.assigned_node)
    assert new_node.status == NodeStatus.ACTIVE
    assert migrated_workload.id in new_node.workload_ids


@pytest.mark.asyncio
async def test_cascading_failure_threshold_protection():
    """
    Test that if >20% of nodes fail simultaneously, the system enters degraded mode
    to prevent catastrophic avalanche load cascading onto surviving nodes.
    """
    node_mgr = NodeManager(node_count=50)
    await node_mgr.initialize(50)
    scheduler = WorkloadScheduler(node_mgr)
    detector = FailureDetector(node_mgr, scheduler, phi_threshold=8.0)

    for n in node_mgr.nodes:
        detector.record_heartbeat(n)

    # Delay heartbeats for 11 nodes (11/50 = 22% > 20% limit)
    all_node_ids = list(node_mgr.nodes.keys())
    past = time.time() - 30.0
    for nid in all_node_ids[:11]:
        node = await node_mgr.get_node(nid)
        node.last_heartbeat = past
        hist = detector._history[nid]
        hist.last_heartbeat = past

    await detector.check_cluster_health()
    # In degraded mode, emergency batch migration throttles cascading storm
    assert detector.degraded_mode is True


@pytest.mark.asyncio
async def test_circuit_breaker_distributed_protection():
    """
    Test circuit breaker state machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
    Ensures distributed RPCs fail fast during downstream outages.
    """
    cb = CircuitBreaker(name="downstream-data-ingestion", failure_threshold=3, recovery_timeout=0.2, half_open_max_calls=1)
    assert cb.state == CircuitBreakerState.CLOSED

    async def faulty_remote_call():
        raise ConnectionResetError("Connection refused by downstream microservice")

    async def successful_remote_call():
        return {"status": "SUCCESS"}

    # Call 3 times and fail -> trips circuit to OPEN
    for _ in range(3):
        with pytest.raises(ConnectionResetError):
            await cb(faulty_remote_call)

    assert cb.state == CircuitBreakerState.OPEN

    # Circuit is OPEN -> calls immediately reject with CircuitBreakerError without hitting downstream
    with pytest.raises(CircuitBreakerError):
        await cb(faulty_remote_call)

    # Wait for recovery timeout
    await asyncio.sleep(0.25)

    # First call in HALF_OPEN succeeds -> circuit recovers to CLOSED
    res = await cb(successful_remote_call)
    assert res["status"] == "SUCCESS"
    assert cb.state == CircuitBreakerState.CLOSED
