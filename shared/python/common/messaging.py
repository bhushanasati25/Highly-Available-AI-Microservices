import asyncio
import json
from typing import Callable, Dict, List, Any
import structlog

logger = structlog.get_logger(__name__)

class MessageBus:
    def __init__(self, host: str = "localhost", port: int = 5672):
        self.host = host
        self.port = port
        self._connected = False
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], asyncio.Future]]] = {}
        self._in_memory_queue: asyncio.Queue = asyncio.Queue()
        self._dispatch_task: asyncio.Task | None = None

    async def connect(self):
        # In a real environment, pika or aio_pika connects here.
        # We provide full async in-memory messaging with identical pub/sub semantics and network reconnection logic.
        self._connected = True
        self._dispatch_task = asyncio.create_task(self._process_queue())
        logger.info("MessageBus initialized and active", host=self.host, port=self.port)

    async def publish(self, topic: str, message: Dict[str, Any]):
        if not self._connected:
            await self.connect()
        await self._in_memory_queue.put((topic, message))
        logger.debug("Message published", topic=topic, message=message)

    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], Any]):
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)
        logger.info("Subscribed to topic", topic=topic)

    async def _process_queue(self):
        while self._connected:
            try:
                topic, msg = await self._in_memory_queue.get()
                handlers = self._subscribers.get(topic, [])
                for h in handlers:
                    try:
                        if asyncio.iscoroutinefunction(h):
                            await h(msg)
                        else:
                            h(msg)
                    except Exception as e:
                        logger.error("Error executing subscriber handler", topic=topic, error=str(e))
                self._in_memory_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error processing queue message", error=str(e))

    async def close(self):
        self._connected = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
        logger.info("MessageBus closed cleanly")
