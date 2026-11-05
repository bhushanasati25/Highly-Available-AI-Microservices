from __future__ import annotations

import asyncio
import math
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import structlog

try:
    from .node_manager import NodeManager, NodeStatus
    from .scheduler import WorkloadScheduler
except ImportError:
    from node_manager import NodeManager, NodeStatus
    from scheduler import WorkloadScheduler

logger = structlog.get_logger(__name__)

@dataclass
class HeartbeatHistory:
    node_id: str
    intervals: List[float] = field(default_factory=list)
    last_heartbeat: float = field(default_factory=time.time)
    window_size: int = 20

    def record_heartbeat(self, now: float):
        if self.last_heartbeat > 0:
            interval = now - self.last_heartbeat
            self.intervals.append(interval)
            if len(self.intervals) > self.window_size:
                self.intervals.pop(0)
        self.last_heartbeat = now

    def mean_interval(self) -> float:
        if not self.intervals:
            return 2.0  # default expected heartbeat 2s
        return sum(self.intervals) / len(self.intervals)

    def stddev_interval(self) -> float:
        if len(self.intervals) < 2:
            return 0.5
        mean = self.mean_interval()
        variance = sum((x - mean) ** 2 for x in self.intervals) / (len(self.intervals) - 1)
        return max(0.1, math.sqrt(variance))

class FailureDetector:
    def __init__(
        self,
        node_manager: NodeManager,
        scheduler: WorkloadScheduler,
        phi_threshold: float = 8.0,
        check_interval: float = 1.0
    ):
        self.node_manager = node_manager
        self.scheduler = scheduler
        self.phi_threshold = phi_threshold
        self.check_interval = check_interval
        self._history: Dict[str, HeartbeatHistory] = {}
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self.failure_events: List[Dict[str, Any]] = []
        self.degraded_mode = False

    async def start(self):
        self._running = True
        self._loop_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Phi Accrual Failure Detector started", phi_threshold=self.phi_threshold)

    async def stop(self):
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
        logger.info("Failure Detector stopped.")

    def record_heartbeat(self, node_id: str):
        now = time.time()
        if node_id not in self._history:
            self._history[node_id] = HeartbeatHistory(node_id=node_id, last_heartbeat=now)
        else:
            self._history[node_id].record_heartbeat(now)

    def compute_phi(self, node_id: str, now: float) -> float:
        """
        Compute Phi suspicion level based on elapsed time since last heartbeat.
        Phi = -log10(P_later(t_elapsed))
        Using normal distribution approximation.
        """
        if node_id not in self._history:
            return 0.0

        hist = self._history[node_id]
        t_elapsed = now - hist.last_heartbeat
        mean = hist.mean_interval()
        stddev = hist.stddev_interval()

        # Cumulative probability using complementary error function
        y = (t_elapsed - mean) / (stddev * math.sqrt(2.0))
        # P_later = 0.5 * erfc(y)
        try:
            p_later = 0.5 * math.erfc(y)
            if p_later <= 1e-12:
                return 16.0  # capped high suspicion
            return -math.log10(p_later)
        except Exception:
            return 16.0

    async def _monitoring_loop(self):
        while self._running:
            try:
                await self.check_cluster_health()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Failure Detector loop", error=str(e))
                await asyncio.sleep(1.0)

    async def check_cluster_health(self):
        now = time.time()
        failed_in_cycle = []

        total_nodes = len(self.node_manager.nodes)
        active_nodes = [n for n in self.node_manager.nodes.values() if n.status == NodeStatus.ACTIVE]

        for node in active_nodes:
            phi = self.compute_phi(node.id, now)
            # Heartbeat hard timeout fallback or Phi threshold trip
            if phi >= self.phi_threshold or (now - node.last_heartbeat > 15.0):
                failed_in_cycle.append(node.id)

        # Cascading failure protection (> 20% of cluster failing in single cycle)
        if total_nodes > 0 and (len(failed_in_cycle) / total_nodes) > 0.20:
            self.degraded_mode = True
            logger.warn("CASCADING FAILURE DETECTED: Cluster entering DEGRADED mode",
                        failed_count=len(failed_in_cycle), total_nodes=total_nodes)

        for failed_node_id in failed_in_cycle:
            await self._handle_node_failure(failed_node_id, reason="phi_accrual_timeout")

    async def _handle_node_failure(self, node_id: str, reason: str):
        orphaned_workloads = await self.node_manager.mark_failed(node_id, reason=reason)
        event = {
            "node_id": node_id,
            "timestamp": time.time(),
            "reason": reason,
            "orphaned_workloads_count": len(orphaned_workloads),
            "workloads": list(orphaned_workloads)
        }
        self.failure_events.append(event)
        logger.error("Cluster node marked FAILED", **event)

        # Automated Workload Rescheduling Mechanism across 50 nodes
        rescheduled_ok = 0
        for w_id in orphaned_workloads:
            # If in degraded mode, prioritize critical workloads (priority >= 7)
            wkl = self.scheduler.workloads.get(w_id)
            if self.degraded_mode and wkl and wkl.priority < 7:
                wkl.status = wkl.status.PENDING
                continue

            success = await self.scheduler.reschedule(w_id, reason=f"node_failure:{node_id}")
            if success:
                rescheduled_ok += 1

        logger.info("Automated rescheduling completed for failed node",
                    node_id=node_id, total=len(orphaned_workloads), successful=rescheduled_ok)

    async def simulate_node_failure(self, node_id: str) -> Dict[str, Any]:
        """Directly inject a failure for testing rescheduling across nodes."""
        orphaned = await self.node_manager.mark_failed(node_id, reason="simulated_hardware_crash")
        rescheduled = []
        for w_id in orphaned:
            ok = await self.scheduler.reschedule(w_id, reason="simulated_hardware_crash")
            if ok:
                rescheduled.append(w_id)

        return {
            "failed_node": node_id,
            "orphaned_count": len(orphaned),
            "rescheduled_count": len(rescheduled),
            "rescheduled_ids": rescheduled
        }

    async def simulate_node_recovery(self, node_id: str):
        await self.node_manager.mark_recovered(node_id)
        self.record_heartbeat(node_id)
        logger.info("Simulated node recovery completed", node_id=node_id)
