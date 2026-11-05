import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class NodeHeartbeatRecord:
    node_id: str
    last_seen: float = field(default_factory=time.time)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    gpu_available: int = 0
    alive: bool = True

class HeartbeatMonitor:
    def __init__(self, timeout_seconds: float = 6.0):
        self.timeout_seconds = timeout_seconds
        self._nodes: Dict[str, NodeHeartbeatRecord] = {}

    def record_heartbeat(self, node_id: str, cpu: float = 0.0, mem: float = 0.0, gpu: int = 0):
        now = time.time()
        if node_id not in self._nodes:
            self._nodes[node_id] = NodeHeartbeatRecord(
                node_id=node_id,
                last_seen=now,
                cpu_usage=cpu,
                memory_usage=mem,
                gpu_available=gpu,
                alive=True
            )
            logger.info("New node joined cluster heartbeat", node_id=node_id)
        else:
            rec = self._nodes[node_id]
            rec.last_seen = now
            rec.cpu_usage = cpu
            rec.memory_usage = mem
            rec.gpu_available = gpu
            if not rec.alive:
                rec.alive = True
                logger.info("Node recovered and resuming heartbeat", node_id=node_id)

    def scan_dead_nodes(self) -> List[str]:
        now = time.time()
        dead = []
        for node_id, rec in self._nodes.items():
            if rec.alive and (now - rec.last_seen > self.timeout_seconds):
                rec.alive = False
                dead.append(node_id)
                logger.warn("Node heartbeat timeout detected", node_id=node_id, elapsed=now - rec.last_seen)
        return dead

    def get_node_statuses(self) -> List[Dict]:
        return [
            {
                "node_id": rec.node_id,
                "alive": rec.alive,
                "last_seen_seconds_ago": round(time.time() - rec.last_seen, 1),
                "cpu_usage": rec.cpu_usage,
                "memory_usage": rec.memory_usage,
                "gpu_available": rec.gpu_available,
            }
            for rec in self._nodes.values()
        ]
