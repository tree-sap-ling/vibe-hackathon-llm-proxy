from app.pii.masking import MaskingResult, MaskingVault, mask_text
from app.pii.models import PiiEntity, PiiType
from app.pii.observability import (
    PiiAuditEvent,
    build_pii_audit_event,
    log_pii_audit_event,
)
from app.pii.policy import (
    ConsumerDisabledError,
    ConsumerPolicy,
    PolicyError,
    PolicyRegistry,
    UnknownConsumerError,
)
from app.pii.processor import (
    PiiProcessor,
    PreparedRequest,
    build_processor,
)
from app.pii.metrics import PiiMetrics
from app.pii.registry import DetectorRegistry, build_default_registry

__all__ = [
    "ConsumerDisabledError",
    "ConsumerPolicy",
    "DetectorRegistry",
    "MaskingResult",
    "MaskingVault",
    "PiiAuditEvent",
    "PiiEntity",
    "PiiMetrics",
    "PiiProcessor",
    "PiiType",
    "PolicyError",
    "PolicyRegistry",
    "PreparedRequest",
    "UnknownConsumerError",
    "build_default_registry",
    "build_pii_audit_event",
    "build_processor",
    "log_pii_audit_event",
    "mask_text",
]
