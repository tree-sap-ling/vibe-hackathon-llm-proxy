from dataclasses import dataclass
from time import perf_counter

from app.pii.masking import MaskingVault, mask_text
from app.pii.models import PiiEntity, PiiType
from app.pii.policy import ConsumerPolicy, PolicyRegistry
from app.pii.registry import DetectorRegistry, build_default_registry


@dataclass(frozen=True, slots=True)
class PreparedRequest:
    system_id: str
    masked_text: str
    detected_types: tuple[PiiType, ...]
    entities: tuple[PiiEntity, ...]
    entity_count: int
    demask_enabled: bool
    processing_ms: float
    vault: MaskingVault


class PiiProcessor:
    def __init__(
        self,
        policy_registry: PolicyRegistry,
        detector_registry: DetectorRegistry | None = None,
    ):
        self._policy_registry = policy_registry
        self._detector_registry = (
            detector_registry
            if detector_registry is not None
            else build_default_registry()
        )

    def prepare_request(
        self,
        system_id: str,
        text: str,
    ) -> PreparedRequest:
        started = perf_counter()

        policy = self._policy_registry.get_authorized(
            system_id
        )

        entities = self._detector_registry.detect(
            text,
            enabled_types=set(policy.enabled_types),
        )

        masked = mask_text(
            text,
            entities,
        )

        processing_ms = (
            perf_counter() - started
        ) * 1000.0

        return PreparedRequest(
            system_id=policy.system_id,
            masked_text=masked.text,
            detected_types=masked.detected_types,
            entities=tuple(entities),
            entity_count=masked.entity_count,
            demask_enabled=policy.demask_enabled,
            processing_ms=processing_ms,
            vault=masked.vault,
        )

    @staticmethod
    def finalize_response(
        prepared: PreparedRequest,
        response_text: str,
    ) -> str:
        if not prepared.demask_enabled:
            return response_text

        return prepared.vault.demask(response_text)


def build_processor(
    policies: tuple[ConsumerPolicy, ...],
) -> PiiProcessor:
    return PiiProcessor(
        policy_registry=PolicyRegistry(policies)
    )
