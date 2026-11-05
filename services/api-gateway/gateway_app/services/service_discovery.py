import asyncio
import time
from typing import Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)

class ServiceInstance:
    def __init__(self, service_name: str, url: str):
        self.service_name = service_name
        self.url = url
        self.healthy = True
        self.last_check = time.time()

class ServiceDiscovery:
    def __init__(self):
        self._services: Dict[str, List[ServiceInstance]] = {}
        self._round_robin_idx: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def register(self, service_name: str, url: str):
        async with self._lock:
            if service_name not in self._services:
                self._services[service_name] = []
                self._round_robin_idx[service_name] = 0

            # Prevent duplicate registration
            for inst in self._services[service_name]:
                if inst.url == url:
                    inst.healthy = True
                    return

            self._services[service_name].append(ServiceInstance(service_name, url))
            logger.info("Registered service endpoint", service=service_name, url=url)

    async def get_endpoint(self, service_name: str) -> Optional[str]:
        async with self._lock:
            instances = self._services.get(service_name, [])
            healthy_instances = [inst for inst in instances if inst.healthy]

            if not healthy_instances:
                return None

            idx = self._round_robin_idx[service_name] % len(healthy_instances)
            self._round_robin_idx[service_name] += 1
            return healthy_instances[idx].url

    async def set_healthy(self, service_name: str, url: str, healthy: bool):
        async with self._lock:
            instances = self._services.get(service_name, [])
            for inst in instances:
                if inst.url == url:
                    inst.healthy = healthy
                    inst.last_check = time.time()

service_registry = ServiceDiscovery()
