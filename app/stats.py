import asyncio


class ProxyStats:
    def __init__(self):
        self._lock = asyncio.Lock()

        self.total_requests = 0
        self.completed_requests = 0
        self.overload_rejections = 0
        self.circuit_open_rejections = 0
        self.upstream_errors = 0
        self.upstream_timeouts = 0

        self.token_usage_samples = 0
        self.provider_reported_total_tokens = 0
        self.token_observation_seconds = 0.0

    async def increment(self, field: str):
        async with self._lock:
            current_value = getattr(self, field)
            setattr(self, field, current_value + 1)

    async def record_token_usage(
        self,
        *,
        total_tokens: int,
        observed_seconds: float,
    ) -> bool:
        if (
            isinstance(total_tokens, bool)
            or not isinstance(total_tokens, int)
            or total_tokens < 0
            or observed_seconds <= 0
        ):
            return False

        async with self._lock:
            self.token_usage_samples += 1
            self.provider_reported_total_tokens += total_tokens
            self.token_observation_seconds += observed_seconds

        return True

    async def snapshot(self):
        async with self._lock:
            if self.token_observation_seconds > 0:
                tps = (
                    self.provider_reported_total_tokens
                    / self.token_observation_seconds
                )
            else:
                tps = 0.0

            return {
                "total_requests": self.total_requests,
                "completed_requests": self.completed_requests,
                "overload_rejections": self.overload_rejections,
                "circuit_open_rejections": self.circuit_open_rejections,
                "upstream_errors": self.upstream_errors,
                "upstream_timeouts": self.upstream_timeouts,
                "tps": round(tps, 3),
                "token_usage": {
                    "samples": self.token_usage_samples,
                    "provider_reported_total_tokens": (
                        self.provider_reported_total_tokens
                    ),
                    "observed_seconds": round(
                        self.token_observation_seconds,
                        6,
                    ),
                },
            }
