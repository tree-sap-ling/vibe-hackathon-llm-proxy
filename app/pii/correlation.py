import asyncio
import hashlib
from dataclasses import dataclass

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

    The store is intentionally request-pair oriented:
    it keeps the PreparedRequest/vault required for
    demasking and a SHA-256 digest for idempotent
    retries of the original request.

    This implementation is NOT shared across OS
    processes. Do not run multiple HTTP workers with
    this store.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._records: dict[
            str,
            CorrelationRecord,
        ] = {}

    async def get(
        self,
        payload_id: str,
    ) -> CorrelationRecord | None:
        self._validate_payload_id(payload_id)

        async with self._lock:
            return self._records.get(payload_id)

    async def put_if_absent(
        self,
        *,
        payload_id: str,
        original_payload: str,
        prepared: PreparedRequest,
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
            masked_payload=prepared.masked_text,
            prepared=prepared,
        )

        async with self._lock:
            existing = self._records.get(
                payload_id
            )

            if existing is not None:
                return existing, False

            self._records[
                payload_id
            ] = candidate

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
        record = await self.get(payload_id)

        if record is None:
            raise KeyError(payload_id)

        if record.matches_original(payload):
            return "mask_retry", record

        if record.matches_masked(payload):
            return "demask", record

        raise CorrelationConflictError(
            "payload_id already exists with "
            "different payload"
        )

    async def size(self) -> int:
        async with self._lock:
            return len(self._records)

    @staticmethod
    def _validate_payload_id(
        payload_id: str,
    ) -> None:
        if not payload_id.strip():
            raise ValueError(
                "payload_id must not be empty"
            )
