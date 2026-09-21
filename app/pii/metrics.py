import asyncio
import math
from collections import Counter, deque
from time import perf_counter

from app.pii.processor import PreparedRequest


def _percentile(
    sorted_values: list[float],
    percentile: float,
) -> float:
    if not sorted_values:
        return 0.0

    rank = math.ceil(
        (percentile / 100.0) * len(sorted_values)
    )
    index = max(
        0,
        min(
            rank - 1,
            len(sorted_values) - 1,
        ),
    )

    return sorted_values[index]


class PiiMetrics:
    def __init__(
        self,
        *,
        latency_sample_limit: int = 2048,
    ):
        if latency_sample_limit <= 0:
            raise ValueError(
                "latency_sample_limit must be positive"
            )

        self._lock = asyncio.Lock()
        self._started_at = perf_counter()
        self._latency_samples = deque(
            maxlen=latency_sample_limit
        )
        self._requests_by_type: Counter[str] = (
            Counter()
        )

        self.processed_requests = 0
        self.requests_with_pii = 0
        self.detected_entities = 0
        self.total_processing_ms = 0.0
        self.max_processing_ms = 0.0

    async def record(
        self,
        prepared: PreparedRequest,
    ) -> None:
        async with self._lock:
            self.processed_requests += 1
            self.detected_entities += (
                prepared.entity_count
            )

            if prepared.entity_count > 0:
                self.requests_with_pii += 1

            self.total_processing_ms += (
                prepared.processing_ms
            )
            self.max_processing_ms = max(
                self.max_processing_ms,
                prepared.processing_ms,
            )
            self._latency_samples.append(
                prepared.processing_ms
            )

            for pii_type in prepared.detected_types:
                self._requests_by_type[
                    pii_type.value
                ] += 1

    async def snapshot(self) -> dict[str, object]:
        async with self._lock:
            now = perf_counter()
            elapsed_seconds = max(
                now - self._started_at,
                1e-9,
            )

            samples = sorted(
                self._latency_samples
            )

            average_processing_ms = 0.0

            if self.processed_requests:
                average_processing_ms = (
                    self.total_processing_ms
                    / self.processed_requests
                )

            return {
                "processed_requests": (
                    self.processed_requests
                ),
                "requests_with_pii": (
                    self.requests_with_pii
                ),
                "detected_entities": (
                    self.detected_entities
                ),
                "average_rps_since_start": round(
                    self.processed_requests
                    / elapsed_seconds,
                    3,
                ),
                "processing_ms": {
                    "samples": len(samples),
                    "avg": round(
                        average_processing_ms,
                        3,
                    ),
                    "p50": round(
                        _percentile(
                            samples,
                            50.0,
                        ),
                        3,
                    ),
                    "p95": round(
                        _percentile(
                            samples,
                            95.0,
                        ),
                        3,
                    ),
                    "p99": round(
                        _percentile(
                            samples,
                            99.0,
                        ),
                        3,
                    ),
                    "max": round(
                        self.max_processing_ms,
                        3,
                    ),
                },
                "requests_by_type": dict(
                    sorted(
                        self._requests_by_type.items()
                    )
                ),
            }
