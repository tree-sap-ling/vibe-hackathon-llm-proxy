from dataclasses import dataclass
from typing import Protocol

from app.pii.processor import PreparedRequest


class InfoLogger(Protocol):
    def info(
        self,
        message: str,
        *,
        extra: dict[str, object],
    ) -> None:
        ...


@dataclass(frozen=True, slots=True)
class PiiAuditEvent:
    request_id: str
    system_id: str
    detected_types: tuple[str, ...]
    entity_count: int
    processing_ms: float
    demask_enabled: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "system_id": self.system_id,
            "detected_types": list(self.detected_types),
            "entity_count": self.entity_count,
            "processing_ms": round(self.processing_ms, 3),
            "demask_enabled": self.demask_enabled,
        }


def build_pii_audit_event(
    request_id: str,
    prepared: PreparedRequest,
) -> PiiAuditEvent:
    if not request_id.strip():
        raise ValueError("request_id must not be empty")

    return PiiAuditEvent(
        request_id=request_id,
        system_id=prepared.system_id,
        detected_types=tuple(
            pii_type.value
            for pii_type in prepared.detected_types
        ),
        entity_count=prepared.entity_count,
        processing_ms=prepared.processing_ms,
        demask_enabled=prepared.demask_enabled,
    )


def log_pii_audit_event(
    logger: InfoLogger,
    event: PiiAuditEvent,
) -> None:
    logger.info(
        "pii_processing_completed",
        extra={
            "pii_audit": event.as_dict(),
        },
    )
