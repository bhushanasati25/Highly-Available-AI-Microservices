from typing import Dict, List, Optional
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class ComputeNode:
    node_id: str
    total_cpu: float = 16.0
    total_memory_gb: float = 64.0
    total_gpu: int = 2
    allocated_cpu: float = 0.0
    allocated_memory_gb: float = 0.0
    allocated_gpu: int = 0
    active: bool = True
    assigned_jobs: List[str] = field(default_factory=list)

    @property
    def cpu_utilization(self) -> float:
        return self.allocated_cpu / self.total_cpu if self.total_cpu > 0 else 1.0

    @property
    def memory_utilization(self) -> float:
        return self.allocated_memory_gb / self.total_memory_gb if self.total_memory_gb > 0 else 1.0

    @property
    def composite_load(self) -> float:
        gpu_util = (self.allocated_gpu / self.total_gpu) if self.total_gpu > 0 else 0.0
        return 0.4 * self.cpu_utilization + 0.3 * self.memory_utilization + 0.3 * gpu_util

class WorkloadBalancer:
    def __init__(self):
        self._nodes: Dict[str, ComputeNode] = {}

    def register_node(self, node: ComputeNode):
        self._nodes[node.node_id] = node
        logger.info("Registered compute node", node_id=node.node_id, gpus=node.total_gpu)

    def select_best_node(self, req_cpu: float, req_mem: float, req_gpu: int) -> Optional[str]:
        eligible = []
        for node in self._nodes.values():
            if not node.active:
                continue
            if (node.total_cpu - node.allocated_cpu >= req_cpu and
                node.total_memory_gb - node.allocated_memory_gb >= req_mem and
                node.total_gpu - node.allocated_gpu >= req_gpu):
                eligible.append(node)

        if not eligible:
            return None

        # Least-loaded strategy
        eligible.sort(key=lambda n: n.composite_load)
        return eligible[0].node_id

    def allocate(self, node_id: str, job_id: str, req_cpu: float, req_mem: float, req_gpu: int) -> bool:
        if node_id not in self._nodes:
            return False
        node = self._nodes[node_id]
        node.allocated_cpu += req_cpu
        node.allocated_memory_gb += req_mem
        node.allocated_gpu += req_gpu
        node.assigned_jobs.append(job_id)
        return True

    def release(self, node_id: str, job_id: str, req_cpu: float, req_mem: float, req_gpu: int):
        if node_id in self._nodes:
            node = self._nodes[node_id]
            node.allocated_cpu = max(0.0, node.allocated_cpu - req_cpu)
            node.allocated_memory_gb = max(0.0, node.allocated_memory_gb - req_mem)
            node.allocated_gpu = max(0, node.allocated_gpu - req_gpu)
            if job_id in node.assigned_jobs:
                node.assigned_jobs.remove(job_id)

    def list_nodes(self) -> List[Dict]:
        return [
            {
                "node_id": n.node_id,
                "active": n.active,
                "cpu_util": round(n.cpu_utilization * 100, 1),
                "mem_util": round(n.memory_utilization * 100, 1),
                "allocated_gpu": n.allocated_gpu,
                "total_gpu": n.total_gpu,
                "jobs": list(n.assigned_jobs),
            }
            for n in self._nodes.values()
        ]
