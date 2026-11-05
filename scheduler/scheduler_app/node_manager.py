"""
Node Manager — lifecycle, resource tracking, and health management for a
heterogeneous cluster of simulated compute nodes.
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    FAILED = "FAILED"
    MAINTENANCE = "MAINTENANCE"


# ---------------------------------------------------------------------------
# Node dataclass
# ---------------------------------------------------------------------------

@dataclass
class Node:
    id: str
    hostname: str
    ip_address: str
    port: int
    status: NodeStatus = NodeStatus.ACTIVE

    # Total (immutable) resources
    total_cpu: float = 8.0
    total_memory: float = 32.0        # GB
    total_gpu: int = 0
    total_disk: float = 500.0         # GB

    # Available (mutable) resources
    available_cpu: float = 8.0
    available_memory: float = 32.0
    available_gpu: int = 0
    available_disk: float = 500.0

    labels: dict[str, str] = field(default_factory=dict)
    workload_ids: list[str] = field(default_factory=list)

    last_heartbeat: float = field(default_factory=time.time)
    failure_count: int = 0
    joined_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def cpu_utilization(self) -> float:
        if self.total_cpu == 0:
            return 0.0
        return (self.total_cpu - self.available_cpu) / self.total_cpu

    @property
    def memory_utilization(self) -> float:
        if self.total_memory == 0:
            return 0.0
        return (self.total_memory - self.available_memory) / self.total_memory

    @property
    def overall_utilization(self) -> float:
        return (self.cpu_utilization + self.memory_utilization) / 2.0

    def can_fit(self, cpu: float, memory: float, gpu: int = 0, disk: float = 0.0) -> bool:
        return (
            self.available_cpu >= cpu
            and self.available_memory >= memory
            and self.available_gpu >= gpu
            and self.available_disk >= disk
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "port": self.port,
            "status": self.status.value,
            "total_cpu": self.total_cpu,
            "available_cpu": round(self.available_cpu, 2),
            "total_memory": self.total_memory,
            "available_memory": round(self.available_memory, 2),
            "total_gpu": self.total_gpu,
            "available_gpu": self.available_gpu,
            "total_disk": self.total_disk,
            "available_disk": round(self.available_disk, 2),
            "labels": self.labels,
            "workload_count": len(self.workload_ids),
            "workload_ids": list(self.workload_ids),
            "cpu_utilization": round(self.cpu_utilization * 100, 1),
            "memory_utilization": round(self.memory_utilization * 100, 1),
            "overall_utilization": round(self.overall_utilization * 100, 1),
            "last_heartbeat": self.last_heartbeat,
            "failure_count": self.failure_count,
            "joined_at": self.joined_at,
        }


# ---------------------------------------------------------------------------
# Resource profile templates for heterogeneous cluster
# ---------------------------------------------------------------------------

_RESOURCE_PROFILES: list[dict[str, Any]] = [
    # Standard compute (30 nodes)
    {"cpu": 8,  "memory": 32,  "gpu": 0, "disk": 500,  "labels": {"tier": "standard", "type": "compute"}},
    # High-memory (8 nodes)
    {"cpu": 16, "memory": 128, "gpu": 0, "disk": 1000, "labels": {"tier": "high-memory", "type": "compute"}},
    # GPU nodes (8 nodes)
    {"cpu": 16, "memory": 64,  "gpu": 4, "disk": 1000, "labels": {"tier": "gpu", "type": "gpu-compute"}},
    # Small edge (4 nodes)
    {"cpu": 4,  "memory": 16,  "gpu": 0, "disk": 250,  "labels": {"tier": "edge", "type": "compute"}},
]

_PROFILE_COUNTS = [30, 8, 8, 4]  # sums to 50


# ---------------------------------------------------------------------------
# NodeManager
# ---------------------------------------------------------------------------

class NodeManager:
    """Manages a cluster of compute nodes with resource tracking and lifecycle."""

    def __init__(self, node_count: int = 50) -> None:
        self._lock = asyncio.Lock()
        self.nodes: dict[str, Node] = {}
        self._node_count = node_count
        self._heartbeat_timeout: float = 15.0   # seconds

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def initialize(self, node_count: int | None = None) -> None:
        count = node_count or self._node_count
        async with self._lock:
            self.nodes.clear()
            idx = 0
            for profile, profile_count in zip(_RESOURCE_PROFILES, _PROFILE_COUNTS):
                actual = int(profile_count * count / 50) or 1
                for _ in range(actual):
                    if idx >= count:
                        break
                    node = self._make_node(idx, profile)
                    self.nodes[node.id] = node
                    idx += 1
                if idx >= count:
                    break
            # Fill remaining with standard profile
            while idx < count:
                node = self._make_node(idx, _RESOURCE_PROFILES[0])
                self.nodes[node.id] = node
                idx += 1

        await logger.ainfo(
            "cluster_initialized",
            node_count=len(self.nodes),
            total_cpu=self.total_cpu,
            total_memory=self.total_memory,
            total_gpu=self.total_gpu,
        )

    def _make_node(self, index: int, profile: dict[str, Any]) -> Node:
        node_id = f"node-{index:03d}"
        return Node(
            id=node_id,
            hostname=f"worker-{index:03d}.cluster.local",
            ip_address=f"10.0.{index // 256}.{index % 256}",
            port=8000 + index,
            total_cpu=float(profile["cpu"]),
            available_cpu=float(profile["cpu"]),
            total_memory=float(profile["memory"]),
            available_memory=float(profile["memory"]),
            total_gpu=int(profile["gpu"]),
            available_gpu=int(profile["gpu"]),
            total_disk=float(profile["disk"]),
            available_disk=float(profile["disk"]),
            labels=dict(profile["labels"]),
        )

    # ------------------------------------------------------------------
    # Node lifecycle
    # ------------------------------------------------------------------

    async def join_cluster(
        self,
        hostname: str | None = None,
        cpu: float = 8.0,
        memory: float = 32.0,
        gpu: int = 0,
        disk: float = 500.0,
        labels: dict[str, str] | None = None,
    ) -> Node:
        async with self._lock:
            node_id = f"node-{uuid.uuid4().hex[:8]}"
            node = Node(
                id=node_id,
                hostname=hostname or f"{node_id}.cluster.local",
                ip_address=f"10.0.{random.randint(1, 254)}.{random.randint(1, 254)}",
                port=random.randint(8000, 9000),
                total_cpu=cpu,
                available_cpu=cpu,
                total_memory=memory,
                available_memory=memory,
                total_gpu=gpu,
                available_gpu=gpu,
                total_disk=disk,
                available_disk=disk,
                labels=labels or {},
            )
            self.nodes[node_id] = node
            await logger.ainfo("node_joined", node_id=node_id, hostname=node.hostname)
            return node

    async def leave_cluster(self, node_id: str) -> list[str]:
        """Remove node; returns workload IDs that were on it."""
        async with self._lock:
            node = self.nodes.pop(node_id, None)
            if node is None:
                raise NodeNotFoundError(node_id)
            orphaned = list(node.workload_ids)
            await logger.ainfo("node_left", node_id=node_id, orphaned_workloads=len(orphaned))
            return orphaned

    async def drain_node(self, node_id: str) -> list[str]:
        """Set node to DRAINING; returns workload IDs that need rescheduling."""
        async with self._lock:
            node = self._get_node_locked(node_id)
            node.status = NodeStatus.DRAINING
            workloads = list(node.workload_ids)
            await logger.ainfo("node_draining", node_id=node_id, workloads_to_migrate=len(workloads))
            return workloads

    async def mark_failed(self, node_id: str, reason: str = "heartbeat_timeout") -> list[str]:
        """Mark node as FAILED; returns orphaned workload IDs."""
        async with self._lock:
            node = self._get_node_locked(node_id)
            node.status = NodeStatus.FAILED
            node.failure_count += 1
            orphaned = list(node.workload_ids)
            await logger.ainfo(
                "node_failed",
                node_id=node_id,
                reason=reason,
                orphaned_workloads=len(orphaned),
                failure_count=node.failure_count,
            )
            return orphaned

    async def mark_recovered(self, node_id: str) -> None:
        async with self._lock:
            node = self._get_node_locked(node_id)
            node.status = NodeStatus.ACTIVE
            node.last_heartbeat = time.time()
            await logger.ainfo("node_recovered", node_id=node_id)

    async def set_maintenance(self, node_id: str) -> list[str]:
        """Put node in maintenance mode; returns workload IDs to migrate."""
        async with self._lock:
            node = self._get_node_locked(node_id)
            node.status = NodeStatus.MAINTENANCE
            workloads = list(node.workload_ids)
            await logger.ainfo("node_maintenance", node_id=node_id, workloads_to_migrate=len(workloads))
            return workloads

    async def activate_node(self, node_id: str) -> None:
        async with self._lock:
            node = self._get_node_locked(node_id)
            node.status = NodeStatus.ACTIVE
            node.last_heartbeat = time.time()
            await logger.ainfo("node_activated", node_id=node_id)

    # ------------------------------------------------------------------
    # Resource tracking
    # ------------------------------------------------------------------

    async def allocate_resources(
        self, node_id: str, cpu: float, memory: float, gpu: int = 0, disk: float = 0.0, workload_id: str | None = None
    ) -> bool:
        async with self._lock:
            node = self._get_node_locked(node_id)
            if not node.can_fit(cpu, memory, gpu, disk):
                return False
            node.available_cpu -= cpu
            node.available_memory -= memory
            node.available_gpu -= gpu
            node.available_disk -= disk
            if workload_id and workload_id not in node.workload_ids:
                node.workload_ids.append(workload_id)
            return True

    async def release_resources(
        self, node_id: str, cpu: float, memory: float, gpu: int = 0, disk: float = 0.0, workload_id: str | None = None
    ) -> None:
        async with self._lock:
            node = self._get_node_locked(node_id)
            node.available_cpu = min(node.total_cpu, node.available_cpu + cpu)
            node.available_memory = min(node.total_memory, node.available_memory + memory)
            node.available_gpu = min(node.total_gpu, node.available_gpu + gpu)
            node.available_disk = min(node.total_disk, node.available_disk + disk)
            if workload_id and workload_id in node.workload_ids:
                node.workload_ids.remove(workload_id)

    async def get_utilization(self, node_id: str) -> dict[str, float]:
        async with self._lock:
            node = self._get_node_locked(node_id)
            return {
                "cpu_utilization": round(node.cpu_utilization * 100, 1),
                "memory_utilization": round(node.memory_utilization * 100, 1),
                "overall_utilization": round(node.overall_utilization * 100, 1),
            }

    # ------------------------------------------------------------------
    # Heartbeats
    # ------------------------------------------------------------------

    async def update_heartbeat(self, node_id: str) -> None:
        async with self._lock:
            node = self._get_node_locked(node_id)
            node.last_heartbeat = time.time()

    async def check_heartbeat_timeout(self, node_id: str) -> bool:
        """Return True if the node has timed out."""
        async with self._lock:
            node = self._get_node_locked(node_id)
            return (time.time() - node.last_heartbeat) > self._heartbeat_timeout

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    async def get_active_nodes(self) -> list[Node]:
        async with self._lock:
            return [n for n in self.nodes.values() if n.status == NodeStatus.ACTIVE]

    async def get_nodes_by_status(self, status: NodeStatus) -> list[Node]:
        async with self._lock:
            return [n for n in self.nodes.values() if n.status == status]

    async def get_node(self, node_id: str) -> Node:
        async with self._lock:
            return self._get_node_locked(node_id)

    async def get_all_nodes(self) -> list[Node]:
        async with self._lock:
            return list(self.nodes.values())

    async def get_nodes_with_label(self, key: str, value: str) -> list[Node]:
        async with self._lock:
            return [
                n for n in self.nodes.values()
                if n.status == NodeStatus.ACTIVE and n.labels.get(key) == value
            ]

    async def get_nodes_with_capacity(
        self, cpu: float, memory: float, gpu: int = 0, disk: float = 0.0
    ) -> list[Node]:
        async with self._lock:
            return [
                n for n in self.nodes.values()
                if n.status == NodeStatus.ACTIVE and n.can_fit(cpu, memory, gpu, disk)
            ]

    # ------------------------------------------------------------------
    # Anti-affinity
    # ------------------------------------------------------------------

    async def check_anti_affinity(self, node_id: str, anti_affinity_labels: dict[str, str], current_workload_labels: dict[str, str] | None = None) -> bool:
        """Return True if the node does NOT violate anti-affinity rules.

        For simplicity the anti_affinity_labels is compared against the node's
        labels.  A conflict means the node carries a label that matches one of
        the anti-affinity labels – i.e. we should NOT schedule here.
        """
        async with self._lock:
            node = self._get_node_locked(node_id)
            for key, val in anti_affinity_labels.items():
                if node.labels.get(key) == val:
                    return False  # conflict
            return True  # no conflict

    # ------------------------------------------------------------------
    # Cluster-wide metrics
    # ------------------------------------------------------------------

    @property
    def total_cpu(self) -> float:
        return sum(n.total_cpu for n in self.nodes.values())

    @property
    def available_cpu(self) -> float:
        return sum(n.available_cpu for n in self.nodes.values())

    @property
    def total_memory(self) -> float:
        return sum(n.total_memory for n in self.nodes.values())

    @property
    def available_memory(self) -> float:
        return sum(n.available_memory for n in self.nodes.values())

    @property
    def total_gpu(self) -> int:
        return sum(n.total_gpu for n in self.nodes.values())

    @property
    def available_gpu(self) -> int:
        return sum(n.available_gpu for n in self.nodes.values())

    def node_count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {s.value: 0 for s in NodeStatus}
        for n in self.nodes.values():
            counts[n.status.value] += 1
        return counts

    def cluster_utilization(self) -> dict[str, Any]:
        total_cpu = self.total_cpu
        total_mem = self.total_memory
        return {
            "total_nodes": len(self.nodes),
            "nodes_by_status": self.node_count_by_status(),
            "cpu": {
                "total": total_cpu,
                "available": round(self.available_cpu, 2),
                "used": round(total_cpu - self.available_cpu, 2),
                "utilization_pct": round(((total_cpu - self.available_cpu) / total_cpu * 100) if total_cpu else 0, 1),
            },
            "memory": {
                "total": total_mem,
                "available": round(self.available_memory, 2),
                "used": round(total_mem - self.available_memory, 2),
                "utilization_pct": round(((total_mem - self.available_memory) / total_mem * 100) if total_mem else 0, 1),
            },
            "gpu": {
                "total": self.total_gpu,
                "available": self.available_gpu,
                "used": self.total_gpu - self.available_gpu,
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_node_locked(self, node_id: str) -> Node:
        node = self.nodes.get(node_id)
        if node is None:
            raise NodeNotFoundError(node_id)
        return node


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class NodeNotFoundError(Exception):
    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__(f"Node not found: {node_id}")


class InsufficientResourcesError(Exception):
    def __init__(self, message: str = "Insufficient cluster resources") -> None:
        super().__init__(message)
