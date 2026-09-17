import asyncio


class ProxyStats:
    def __init__(self):
        self._lock = asyncio.Lock()

        self.total_requests = 0
        self.completed_requests = 0
        self.overload_rejections = 0
        self.upstream_errors = 0
        self.upstream_timeouts = 0

    async def increment(self, field: str):
        async with self._lock:
            current_value = getattr(self, field)
            setattr(self, field, current_value + 1)

    async def snapshot(self):
        async with self._lock:
            return {
                "total_requests": self.total_requests,
                "completed_requests": self.completed_requests,
                "overload_rejections": self.overload_rejections,
                "upstream_errors": self.upstream_errors,
                "upstream_timeouts": self.upstream_timeouts,
            }
