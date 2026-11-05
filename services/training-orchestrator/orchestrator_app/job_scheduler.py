import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import time
import structlog

logger = structlog.get_logger(__name__)

@dataclass(order=True)
class QueuedJob:
    # Priority queue: invert priority so higher numerical priority pops first
    sort_key: tuple[int, float] = field(init=False)
    priority: int = 5
    submitted_at: float = field(default_factory=time.time)
    job_id: str = field(compare=False, default="")
    model_type: str = field(compare=False, default="")
    req_cpu: float = field(compare=False, default=4.0)
    req_mem: float = field(compare=False, default=16.0)
    req_gpu: int = field(compare=False, default=1)

    def __post_init__(self):
        self.sort_key = (-self.priority, self.submitted_at)

class JobScheduler:
    def __init__(self):
        self._queue: List[QueuedJob] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, job: QueuedJob):
        async with self._lock:
            self._queue.append(job)
            self._queue.sort()
            logger.info("Enqueued training job", job_id=job.job_id, priority=job.priority, qsize=len(self._queue))

    async def pop_next(self) -> Optional[QueuedJob]:
        async with self._lock:
            if not self._queue:
                return None
            return self._queue.pop(0)

    async def remove(self, job_id: str) -> bool:
        async with self._lock:
            for i, j in enumerate(self._queue):
                if j.job_id == job_id:
                    self._queue.pop(i)
                    return True
            return False

    async def queue_length(self) -> int:
        async with self._lock:
            return len(self._queue)
