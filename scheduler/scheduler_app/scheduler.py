from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import structlog

try:
    from .node_manager import NodeManager, Node, NodeStatus
except ImportError:
    from node_manager import NodeManager, Node, NodeStatus

logger = structlog.get_logger(__name__)

class SchedulingAlgorithm(str, Enum):
    LEAST_LOADED = "LEAST_LOADED"
    ROUND_ROBIN = "ROUND_ROBIN"
    RESOURCE_FIT = "RESOURCE_FIT"
    SPREAD = "SPREAD"
    RANDOM = "RANDOM"

class WorkloadStatus(str, Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    RESCHEDULING = "RESCHEDULING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    QUARANTINED = "QUARANTINED"

@dataclass
class Workload:
    id: str
    name: str
    required_cpu: float
    required_memory: float  # GB
    required_gpu: int = 0
    required_disk: float = 0.0  # GB
    priority: int = 5  # 1 to 10
    status: WorkloadStatus = WorkloadStatus.PENDING
    assigned_node: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    affinity_labels: Dict[str, str] = field(default_factory=dict)
    anti_affinity_labels: Dict[str, str] = field(default_factory=dict)
    reschedule_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "required_cpu": self.required_cpu,
            "required_memory": self.required_memory,
            "required_gpu": self.required_gpu,
            "required_disk": self.required_disk,
            "priority": self.priority,
            "status": self.status.value,
            "assigned_node": self.assigned_node,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "affinity_labels": self.affinity_labels,
            "anti_affinity_labels": self.anti_affinity_labels,
            "reschedule_count": len(self.reschedule_history),
        }

@dataclass
class QuarantinedWorkload:
    workload: Workload
    quarantined_at: float
    reason: str
    error_trace: Optional[str] = None
    node_history: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workload_id": self.workload.id,
            "workload": self.workload.to_dict(),
            "quarantined_at": self.quarantined_at,
            "reason": self.reason,
            "error_trace": self.error_trace,
            "node_history": self.node_history,
        }

class DeadLetterQueue:
    """
    Dead-Letter Queue (DLQ) & Quarantine Manager for poisoned / unrecoverable AI workloads.
    Prevents repeated cascading crashes across healthy cluster nodes by isolating
    failing tasks and maintaining forensic failure history for operator audit and replay.
    """
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._quarantine: Dict[str, QuarantinedWorkload] = {}

    def quarantine(self, workload: Workload, reason: str, error_trace: Optional[str] = None) -> QuarantinedWorkload:
        workload.status = WorkloadStatus.QUARANTINED
        node_history = [str(h.get("from_node")) for h in workload.reschedule_history if h.get("from_node")]
        if workload.assigned_node:
            node_history.append(str(workload.assigned_node))
            workload.assigned_node = None

        qw = QuarantinedWorkload(
            workload=workload,
            quarantined_at=time.time(),
            reason=reason,
            error_trace=error_trace or f"Exceeded max_retries ({workload.max_retries}) across nodes: {node_history}",
            node_history=node_history
        )
        self._quarantine[workload.id] = qw
        logger.warning(
            "Workload isolated in Dead-Letter Queue (DLQ)",
            workload_id=workload.id,
            reason=reason,
            node_history=node_history,
        )
        return qw

    def list_all(self) -> List[Dict[str, Any]]:
        return [q.to_dict() for q in self._quarantine.values()]

    def get(self, workload_id: str) -> Optional[QuarantinedWorkload]:
        return self._quarantine.get(workload_id)

    def remove(self, workload_id: str) -> Optional[QuarantinedWorkload]:
        return self._quarantine.pop(workload_id, None)

    def clear(self):
        self._quarantine.clear()

    def count(self) -> int:
        return len(self._quarantine)

class WorkloadScheduler:
    def __init__(self, node_manager: NodeManager, default_algorithm: SchedulingAlgorithm = SchedulingAlgorithm.LEAST_LOADED):
        self.node_manager = node_manager
        self.algorithm = default_algorithm
        self.workloads: Dict[str, Workload] = {}
        self.dlq = DeadLetterQueue()
        self._lock = asyncio.Lock()
        self._rr_index = 0
        self.total_scheduled_count = 0
        self.total_rescheduled_count = 0

    async def schedule(
        self,
        name: str,
        required_cpu: float,
        required_memory: float,
        required_gpu: int = 0,
        required_disk: float = 0.0,
        priority: int = 5,
        affinity: Optional[Dict[str, str]] = None,
        anti_affinity: Optional[Dict[str, str]] = None,
        algorithm: Optional[SchedulingAlgorithm] = None,
    ) -> Workload:
        async with self._lock:
            workload_id = f"wkl-{uuid.uuid4().hex[:10]}"
            workload = Workload(
                id=workload_id,
                name=name,
                required_cpu=required_cpu,
                required_memory=required_memory,
                required_gpu=required_gpu,
                required_disk=required_disk,
                priority=priority,
                affinity_labels=affinity or {},
                anti_affinity_labels=anti_affinity or {},
            )
            self.workloads[workload_id] = workload

            algo = algorithm or self.algorithm
            node_id = await self._find_node_for_workload(workload, algo)

            if node_id:
                success = await self.node_manager.allocate_resources(
                    node_id, workload.required_cpu, workload.required_memory,
                    workload.required_gpu, workload.required_disk, workload.id
                )
                if success:
                    workload.assigned_node = node_id
                    workload.status = WorkloadStatus.SCHEDULED
                    workload.started_at = time.time()
                    self.total_scheduled_count += 1
                    logger.info("Workload scheduled successfully", workload_id=workload_id, node_id=node_id, algo=algo.value)
                    return workload

            # Attempt preemption if priority is high (> 7)
            if priority >= 8:
                preempted = await self._attempt_preemption(workload)
                if preempted:
                    return workload

            workload.status = WorkloadStatus.PENDING
            logger.warn("Workload queued in PENDING state (insufficient cluster capacity)", workload_id=workload_id)
            return workload

    async def reschedule(self, workload_id: str, reason: str = "node_failure") -> bool:
        async with self._lock:
            if workload_id not in self.workloads:
                logger.error("Cannot reschedule: workload not found", workload_id=workload_id)
                return False

            wkl = self.workloads[workload_id]
            if wkl.retry_count >= wkl.max_retries:
                old_node = wkl.assigned_node
                if old_node and old_node in self.node_manager.nodes:
                    try:
                        await self.node_manager.release_resources(
                            old_node, wkl.required_cpu, wkl.required_memory,
                            wkl.required_gpu, wkl.required_disk, wkl.id
                        )
                    except Exception:
                        pass
                self.dlq.quarantine(
                    wkl,
                    reason=f"Exceeded max_retries limit ({wkl.max_retries}) during reschedule attempt ({reason})"
                )
                logger.error("Workload exceeded max retries, moved to DLQ (QUARANTINED)", workload_id=workload_id)
                return False

            old_node = wkl.assigned_node
            wkl.retry_count += 1
            wkl.status = WorkloadStatus.RESCHEDULING

            # Release previous node resources if still registered
            if old_node and old_node in self.node_manager.nodes:
                try:
                    await self.node_manager.release_resources(
                        old_node, wkl.required_cpu, wkl.required_memory,
                        wkl.required_gpu, wkl.required_disk, wkl.id
                    )
                except Exception:
                    pass

            # Exclude old failed node from target selection
            target_node = await self._find_node_for_workload(wkl, self.algorithm, exclude_node=old_node)
            if target_node:
                allocated = await self.node_manager.allocate_resources(
                    target_node, wkl.required_cpu, wkl.required_memory,
                    wkl.required_gpu, wkl.required_disk, wkl.id
                )
                if allocated:
                    wkl.assigned_node = target_node
                    wkl.status = WorkloadStatus.SCHEDULED
                    wkl.reschedule_history.append({
                        "from_node": old_node,
                        "to_node": target_node,
                        "timestamp": time.time(),
                        "reason": reason
                    })
                    self.total_rescheduled_count += 1
                    logger.info("Workload rescheduled to new node", workload_id=workload_id, from_node=old_node, to_node=target_node, attempt=wkl.retry_count)
                    return True

            wkl.status = WorkloadStatus.PENDING
            logger.warn("Rescheduling deferred: no target node currently fits workload", workload_id=workload_id)
            return False

    async def deschedule(self, workload_id: str) -> bool:
        async with self._lock:
            if workload_id not in self.workloads:
                return False
            wkl = self.workloads[workload_id]
            if wkl.assigned_node:
                await self.node_manager.release_resources(
                    wkl.assigned_node, wkl.required_cpu, wkl.required_memory,
                    wkl.required_gpu, wkl.required_disk, wkl.id
                )
            wkl.status = WorkloadStatus.CANCELLED
            wkl.assigned_node = None
            return True

    async def replay_quarantined(self, workload_id: str) -> Optional[Workload]:
        """
        Operator replay of a quarantined DLQ workload after defect remediation or capacity adjustment.
        """
        async with self._lock:
            q_item = self.dlq.get(workload_id)
            if not q_item:
                return None

            self.dlq.remove(workload_id)
            wkl = q_item.workload
            wkl.retry_count = 0
            wkl.status = WorkloadStatus.PENDING
            wkl.assigned_node = None

            node_id = await self._find_node_for_workload(wkl, self.algorithm)
            if node_id:
                allocated = await self.node_manager.allocate_resources(
                    node_id, wkl.required_cpu, wkl.required_memory,
                    wkl.required_gpu, wkl.required_disk, wkl.id
                )
                if allocated:
                    wkl.assigned_node = node_id
                    wkl.status = WorkloadStatus.SCHEDULED
                    wkl.started_at = time.time()
                    self.total_scheduled_count += 1
                    logger.info("Quarantined workload replayed and scheduled", workload_id=workload_id, node_id=node_id)
                    return wkl

            logger.info("Quarantined workload replayed and placed in PENDING queue", workload_id=workload_id)
            return wkl

    async def batch_schedule(self, workload_defs: List[Dict[str, Any]]) -> List[Workload]:
        # First-fit-decreasing bin packing: sort workloads by composite resource size descending
        sorted_defs = sorted(
            workload_defs,
            key=lambda w: (w.get("required_gpu", 0) * 10.0 + w.get("required_cpu", 1.0) + w.get("required_memory", 1.0) / 4.0),
            reverse=True
        )

        results = []
        for w_def in sorted_defs:
            wkl = await self.schedule(
                name=w_def["name"],
                required_cpu=w_def.get("required_cpu", 2.0),
                required_memory=w_def.get("required_memory", 8.0),
                required_gpu=w_def.get("required_gpu", 0),
                required_disk=w_def.get("required_disk", 10.0),
                priority=w_def.get("priority", 5),
                affinity=w_def.get("affinity"),
                anti_affinity=w_def.get("anti_affinity"),
            )
            results.append(wkl)
        return results

    async def _find_node_for_workload(
        self,
        wkl: Workload,
        algo: SchedulingAlgorithm,
        exclude_node: Optional[str] = None
    ) -> Optional[str]:
        eligible: List[Node] = []

        for node in self.node_manager.nodes.values():
            if node.id == exclude_node:
                continue
            if node.status != NodeStatus.ACTIVE:
                continue
            if not node.can_fit(wkl.required_cpu, wkl.required_memory, wkl.required_gpu, wkl.required_disk):
                continue

            # Affinity check
            if wkl.affinity_labels:
                match = all(node.labels.get(k) == v for k, v in wkl.affinity_labels.items())
                if not match:
                    continue

            # Anti-affinity check
            if wkl.anti_affinity_labels:
                mismatch = any(node.labels.get(k) == v for k, v in wkl.anti_affinity_labels.items())
                if mismatch:
                    continue

            eligible.append(node)

        if not eligible:
            return None

        if algo == SchedulingAlgorithm.LEAST_LOADED:
            eligible.sort(key=lambda n: n.overall_utilization)
            return eligible[0].id

        elif algo == SchedulingAlgorithm.ROUND_ROBIN:
            self._rr_index = (self._rr_index + 1) % len(eligible)
            return eligible[self._rr_index].id

        elif algo == SchedulingAlgorithm.RESOURCE_FIT:
            # Best-fit bin packing: pick node that leaves least remaining CPU
            eligible.sort(key=lambda n: (n.available_cpu - wkl.required_cpu))
            return eligible[0].id

        elif algo == SchedulingAlgorithm.SPREAD:
            # Spread across nodes with lowest active workload count
            eligible.sort(key=lambda n: len(n.workload_ids))
            return eligible[0].id

        elif algo == SchedulingAlgorithm.RANDOM:
            return random.choice(eligible).id

        return eligible[0].id

    async def _attempt_preemption(self, high_prio_wkl: Workload) -> bool:
        # Look for a node where evicting lower-priority workloads allows high_prio_wkl to fit
        for node in self.node_manager.nodes.values():
            if node.status != NodeStatus.ACTIVE:
                continue

            preemptable_candidates = []
            for w_id in node.workload_ids:
                cand = self.workloads.get(w_id)
                if cand and cand.priority < high_prio_wkl.priority:
                    preemptable_candidates.append(cand)

            if not preemptable_candidates:
                continue

            # Try evicting candidates
            for cand in preemptable_candidates:
                await self.node_manager.release_resources(
                    node.id, cand.required_cpu, cand.required_memory,
                    cand.required_gpu, cand.required_disk, cand.id
                )
                cand.status = WorkloadStatus.PENDING
                cand.assigned_node = None
                logger.info("Preempted lower-priority workload", victim_id=cand.id, for_workload=high_prio_wkl.id)

                if node.can_fit(high_prio_wkl.required_cpu, high_prio_wkl.required_memory,
                                high_prio_wkl.required_gpu, high_prio_wkl.required_disk):
                    await self.node_manager.allocate_resources(
                        node.id, high_prio_wkl.required_cpu, high_prio_wkl.required_memory,
                        high_prio_wkl.required_gpu, high_prio_wkl.required_disk, high_prio_wkl.id
                    )
                    high_prio_wkl.assigned_node = node.id
                    high_prio_wkl.status = WorkloadStatus.SCHEDULED
                    return True

        return False
