import pytest
from scheduler_app.node_manager import NodeManager, NodeStatus

@pytest.mark.asyncio
async def test_node_manager_initialization():
    nm = NodeManager(node_count=50)
    await nm.initialize(50)
    assert len(nm.nodes) == 50

    gpu_nodes = [n for n in nm.nodes.values() if n.total_gpu > 0]
    assert len(gpu_nodes) >= 8

    high_mem_nodes = [n for n in nm.nodes.values() if n.total_memory >= 128]
    assert len(high_mem_nodes) >= 8

@pytest.mark.asyncio
async def test_node_lifecycle():
    nm = NodeManager(node_count=5)
    await nm.initialize(5)
    node_id = list(nm.nodes.keys())[0]

    # Drain node
    await nm.drain_node(node_id)
    assert nm.nodes[node_id].status == NodeStatus.DRAINING

    # Mark failed
    await nm.mark_failed(node_id, reason="unit_test")
    assert nm.nodes[node_id].status == NodeStatus.FAILED
    assert nm.nodes[node_id].failure_count == 1

    # Recover
    await nm.mark_recovered(node_id)
    assert nm.nodes[node_id].status == NodeStatus.ACTIVE

@pytest.mark.asyncio
async def test_resource_allocation_and_release():
    nm = NodeManager(node_count=2)
    await nm.initialize(2)
    node_id = list(nm.nodes.keys())[0]
    node = nm.nodes[node_id]

    initial_cpu = node.available_cpu

    # Allocate
    success = await nm.allocate_resources(node_id, cpu=2.0, memory=8.0, gpu=0, workload_id="w-1")
    assert success is True
    assert node.available_cpu == initial_cpu - 2.0
    assert "w-1" in node.workload_ids

    # Release
    await nm.release_resources(node_id, cpu=2.0, memory=8.0, gpu=0, workload_id="w-1")
    assert node.available_cpu == initial_cpu
    assert "w-1" not in node.workload_ids
