import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../shared/python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scheduler_app.node_manager import NodeManager
from scheduler_app.scheduler import WorkloadScheduler
from scheduler_app.failure_detector import FailureDetector

@pytest.fixture
async def cluster():
    mgr = NodeManager(node_count=50)
    await mgr.initialize(50)
    sched = WorkloadScheduler(mgr)
    fd = FailureDetector(mgr, sched)
    for n in mgr.nodes:
        fd.record_heartbeat(n)
    return mgr, sched, fd
