import asyncio
import hashlib
from dataclasses import dataclass
from time import monotonic
from typing import Callable

from app.pii.processor import PreparedRequest


class CorrelationError(Exception):
    pass


class CorrelationConflictError(CorrelationError):
    pass


@dataclass(frozen=True, slots=True)
class CorrelationRecord:
    payload_id: str
    original_digest: str
    masked_payload: str
    prepared: PreparedRequest

    def matches_original(self, payload: str) -> bool:
        return self.original_digest == digest_payload(
            payload
        )

    def matches_masked(self, payload: str) -> bool:
        return self.masked_payload == payload


def digest_payload(payload: str) -> str:
    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


class InMemoryCorrelationStore:
    """
    Single-process correlation store for /process.

    Pending records keep the PreparedRequest/vault
    required for demasking. After the first demask,
    records are retained for a shorter completed TTL
    so checker retries can still be answered.

    Cleanup is lazy and interval-limited to avoid a
    full dictionary scan on every request.

    This implementation is NOT shared across OS
    processes. Do not run multiple HTTP workers with
    this store.
    """

    def __init__(
        self,
        *,
        pending_ttl_seconds: float = 900.0,
        completed_ttl_seconds: float = 120.0,
        cleanup_interval_seconds: float = 5.0,
        clock: Callable[[], float] = monotonic,
    ):
        if pending_ttl_seconds <= 0:
            raise ValueError(
                "pending_ttl_seconds must be positive"
            )

        if completed_ttl_seconds <= 0:
            raise ValueError(
                "completed_ttl_seconds must be positive"
            )

        if cleanup_interval_seconds <= 0:
            raise ValueError(
                "cleanup_interval_seconds must be positive"
            )

        self._pending_ttl_seconds = (
            pending_ttl_seconds
        )
        self._completed_ttl_seconds = (
            completed_ttl_seconds
        )
        self._cleanup_interval_seconds = (
            cleanup_interval_seconds
        )
        self._clock = clock

        self._lock = asyncio.Lock()
        self._records: dict[
            str,
            CorrelationRecord,
        ] = {}
        self._created_at: dict[str, float] = {}
        self._completed_at: dict[str, float] = {}
        self._next_cleanup_at = self._clock()

    async def get(
        self,
        payload_id: str,
    ) -> CorrelationRecord | None:
        self._validate_payload_id(payload_id)

        async with self._lock:
            now = self._clock()
            self._cleanup_if_due_locked(now)
            self._expire_payload_id_if_needed_locked(
                payload_id,
                now,
            )

            return self._records.get(payload_id)

    async def put_if_absent(
        self,
        *,
        payload_id: str,
        original_payload: str,
        prepared: PreparedRequest,
        masked_payload: str | None = None,
    ) -> tuple[
        CorrelationRecord,
        bool,
    ]:
        self._validate_payload_id(payload_id)

        candidate = CorrelationRecord(
            payload_id=payload_id,
            original_digest=digest_payload(
                original_payload
            ),
            masked_payload=(
                prepared.masked_text
                if masked_payload is None
                else masked_payload
            ),
            prepared=prepared,
        )

        async with self._lock:
            now = self._clock()
            self._cleanup_if_due_locked(now)
            self._expire_payload_id_if_needed_locked(
                payload_id,
                now,
            )

            existing = self._records.get(
                payload_id
            )

            if existing is not None:
                return existing, False

            self._records[
                payload_id
            ] = candidate
            self._created_at[
                payload_id
            ] = now

            return candidate, True

    async def resolve_existing(
        self,
        *,
        payload_id: str,
        payload: str,
    ) -> tuple[
        str,
        CorrelationRecord,
    ]:
        self._validate_payload_id(payload_id)

        async with self._lock:
            now = self._clock()
            self._cleanup_if_due_locked(now)
            self._expire_payload_id_if_needed_locked(
                payload_id,
                now,
            )

            record = self._records.get(payload_id)

            if record is None:
                raise KeyError(payload_id)

            if record.matches_original(payload):
                return "mask_retry", record

            if record.matches_masked(payload):
                self._completed_at.setdefault(
                    payload_id,
                    now,
                )
                return "demask", record

            raise CorrelationConflictError(
                "payload_id already exists with "
                "different payload"
            )

    async def cleanup(self) -> int:
        async with self._lock:
            now = self._clock()

            removed = self._cleanup_locked(now)

            self._next_cleanup_at = (
                now
                + self._cleanup_interval_seconds
            )

            return removed

    async def size(self) -> int:
        async with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            self._next_cleanup_at = (
                now
                + self._cleanup_interval_seconds
            )

            return len(self._records)

    def _expire_payload_id_if_needed_locked(
        self,
        payload_id: str,
        now: float,
    ) -> bool:
        if payload_id not in self._records:
            return False

        completed_at = self._completed_at.get(
            payload_id
        )

        if completed_at is not None:
            expired = (
                now - completed_at
                >= self._completed_ttl_seconds
            )
        else:
            created_at = self._created_at[
                payload_id
            ]
            expired = (
                now - created_at
                >= self._pending_ttl_seconds
            )

        if not expired:
            return False

        self._records.pop(
            payload_id,
            None,
        )
        self._created_at.pop(
            payload_id,
            None,
        )
        self._completed_at.pop(
            payload_id,
            None,
        )

        return True

    def _cleanup_if_due_locked(
        self,
        now: float,
    ) -> None:
        if now < self._next_cleanup_at:
            return

        self._cleanup_locked(now)

        self._next_cleanup_at = (
            now
            + self._cleanup_interval_seconds
        )

    def _cleanup_locked(
        self,
        now: float,
    ) -> int:
        expired: list[str] = []

        for payload_id in self._records:
            completed_at = self._completed_at.get(
                payload_id
            )

            if completed_at is not None:
                if (
                    now - completed_at
                    >= self._completed_ttl_seconds
                ):
                    expired.append(payload_id)

                continue

            created_at = self._created_at[
                payload_id
            ]

            if (
                now - created_at
                >= self._pending_ttl_seconds
            ):
                expired.append(payload_id)

        for payload_id in expired:
            self._records.pop(
                payload_id,
                None,
            )
            self._created_at.pop(
                payload_id,
                None,
            )
            self._completed_at.pop(
                payload_id,
                None,
            )

        return len(expired)

    @staticmethod
    def _validate_payload_id(
        payload_id: str,
    ) -> None:
        if not payload_id.strip():
            raise ValueError(
                "payload_id must not be empty"
            )
