import pytest
import time
from scheduler_app.failure_detector import FailureDetector
from scheduler_app.scheduler import WorkloadStatus

@pytest.mark.asyncio
async def test_phi_accrual_detection(cluster):
    mgr, sched, fd = cluster
    node_id = list(mgr.nodes.keys())[0]

    now = time.time()
    phi_initial = fd.compute_phi(node_id, now)
    assert phi_initial < 1.0

    phi_delayed = fd.compute_phi(node_id, now + 15.0)
    assert phi_delayed > fd.phi_threshold

@pytest.mark.asyncio
async def test_automated_workload_rescheduling_on_failure(cluster):
    mgr, sched, fd = cluster

    wkl = await sched.schedule(
        name="critical-training-run",
        required_cpu=4.0,
        required_memory=16.0,
        required_gpu=0,
        priority=8
    )
    assert wkl.status == WorkloadStatus.SCHEDULED
    original_node = wkl.assigned_node
    assert original_node is not None

    res = await fd.simulate_node_failure(original_node)
    assert res["failed_node"] == original_node
    assert res["orphaned_count"] >= 1

    rescheduled_wkl = sched.workloads[wkl.id]
    assert rescheduled_wkl.status == WorkloadStatus.SCHEDULED
    assert rescheduled_wkl.assigned_node != original_node
    assert rescheduled_wkl.retry_count == 1
    assert len(rescheduled_wkl.reschedule_history) == 1
    assert rescheduled_wkl.reschedule_history[0]["from_node"] == original_node
    assert rescheduled_wkl.reschedule_history[0]["to_node"] == rescheduled_wkl.assigned_node
