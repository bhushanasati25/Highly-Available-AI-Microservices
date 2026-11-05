import pytest
from scheduler_app.scheduler import WorkloadScheduler, SchedulingAlgorithm, WorkloadStatus

@pytest.mark.asyncio
async def test_scheduler_algorithms(cluster):
    mgr, sched, _ = cluster

    # Test LEAST_LOADED
    w1 = await sched.schedule(
        name="least-loaded-job",
        required_cpu=4.0,
        required_memory=16.0,
        required_gpu=0,
        algorithm=SchedulingAlgorithm.LEAST_LOADED
    )
    assert w1.status == WorkloadStatus.SCHEDULED
    assert w1.assigned_node is not None

    # Test ROUND_ROBIN
    w2 = await sched.schedule(
        name="rr-job",
        required_cpu=2.0,
        required_memory=8.0,
        required_gpu=0,
        algorithm=SchedulingAlgorithm.ROUND_ROBIN
    )
    assert w2.status == WorkloadStatus.SCHEDULED
    assert w2.assigned_node is not None

@pytest.mark.asyncio
async def test_priority_preemption(cluster):
    mgr, sched, _ = cluster
    low_prio = await sched.schedule(
        name="low-prio",
        required_cpu=6.0,
        required_memory=24.0,
        priority=2
    )
    assert low_prio.status == WorkloadStatus.SCHEDULED

    high_prio = await sched.schedule(
        name="high-prio",
        required_cpu=8.0,
        required_memory=32.0,
        priority=9
    )
    assert high_prio.status == WorkloadStatus.SCHEDULED

@pytest.mark.asyncio
async def test_batch_scheduling(cluster):
    mgr, sched, _ = cluster
    workloads = [
        {"name": f"batch-{i}", "required_cpu": 2.0, "required_memory": 4.0, "priority": 5}
        for i in range(10)
    ]
    results = await sched.batch_schedule(workloads)
    assert len(results) == 10
    for r in results:
        assert r.status == WorkloadStatus.SCHEDULED
