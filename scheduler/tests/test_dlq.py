import pytest
from scheduler_app.scheduler import (
    WorkloadScheduler,
    WorkloadStatus,
    DeadLetterQueue,
    Workload,
)

@pytest.mark.asyncio
async def test_dlq_quarantine_on_max_retries(cluster):
    mgr, sched, _ = cluster

    # Schedule a workload with max_retries = 2
    wkl = await sched.schedule(
        name="flaky-training-checkpoint",
        required_cpu=2.0,
        required_memory=8.0,
        required_gpu=0,
    )
    wkl.max_retries = 2
    assert wkl.status == WorkloadStatus.SCHEDULED
    first_node = wkl.assigned_node

    # Attempt 1: Reschedule after simulated node drop
    res1 = await sched.reschedule(wkl.id, reason="hardware_fault_1")
    assert res1 is True
    assert wkl.retry_count == 1
    assert wkl.status == WorkloadStatus.SCHEDULED

    # Attempt 2: Reschedule after second failure
    res2 = await sched.reschedule(wkl.id, reason="hardware_fault_2")
    assert res2 is True
    assert wkl.retry_count == 2

    # Attempt 3: Exceeds max_retries (2) -> Should be quarantined into DLQ
    res3 = await sched.reschedule(wkl.id, reason="cuda_oom_poison_pill")
    assert res3 is False
    assert wkl.status == WorkloadStatus.QUARANTINED
    assert sched.dlq.count() == 1

    # Inspect quarantined item in DLQ
    dlq_item = sched.dlq.get(wkl.id)
    assert dlq_item is not None
    assert dlq_item.workload.id == wkl.id
    assert "Exceeded max_retries" in dlq_item.reason
    assert len(dlq_item.node_history) >= 2


@pytest.mark.asyncio
async def test_dlq_replay_and_purge(cluster):
    mgr, sched, _ = cluster

    wkl = await sched.schedule(
        name="remedied-workload",
        required_cpu=2.0,
        required_memory=4.0,
    )
    wkl.max_retries = 1

    # First reschedule
    await sched.reschedule(wkl.id, reason="test_failure_1")
    # Second reschedule triggers quarantine
    await sched.reschedule(wkl.id, reason="test_failure_2")

    assert sched.dlq.count() == 1
    assert wkl.status == WorkloadStatus.QUARANTINED

    # Replay from DLQ
    replayed = await sched.replay_quarantined(wkl.id)
    assert replayed is not None
    assert replayed.id == wkl.id
    assert replayed.retry_count == 0
    assert replayed.status in [WorkloadStatus.SCHEDULED, WorkloadStatus.PENDING]
    assert sched.dlq.count() == 0

    # Test explicit manual quarantine & purge
    wkl2 = Workload(
        id="wkl-manual-poison",
        name="poison-pill-task",
        required_cpu=1.0,
        required_memory=2.0,
    )
    sched.dlq.quarantine(wkl2, reason="manual_quarantine_operator_flag")
    assert sched.dlq.count() == 1
    purged = sched.dlq.remove("wkl-manual-poison")
    assert purged is not None
    assert sched.dlq.count() == 0
