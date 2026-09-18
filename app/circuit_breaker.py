import asyncio
import time


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 5.0,
    ):
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout = max(0.0, recovery_timeout)

        self.failure_count = 0
        self.state = "closed"
        self.opened_at = None

        self.lock = asyncio.Lock()

    async def allow_request(self) -> bool:
        async with self.lock:
            if self.state == "closed":
                return True

            if self.state == "open":
                elapsed = time.monotonic() - self.opened_at

                if elapsed < self.recovery_timeout:
                    return False

                self.state = "half_open"
                return True

            # While one half-open probe is running,
            # reject additional requests.
            return False

    async def record_success(self) -> None:
        async with self.lock:
            self.failure_count = 0
            self.state = "closed"
            self.opened_at = None

    async def record_failure(self) -> None:
        async with self.lock:
            if self.state == "half_open":
                self.state = "open"
                self.opened_at = time.monotonic()
                return

            self.failure_count += 1

            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                self.opened_at = time.monotonic()

    async def snapshot(self) -> dict:
        async with self.lock:
            return {
                "state": self.state,
                "failure_count": self.failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            }
