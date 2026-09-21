from collections.abc import Callable, Iterable

from app.pii.models import PiiEntity, PiiType


Detector = Callable[[str], Iterable[PiiEntity]]


class DetectorRegistry:
    def __init__(
        self,
        detectors: Iterable[Detector] = (),
    ):
        self._detectors = list(detectors)

    def register(self, detector: Detector) -> None:
        self._detectors.append(detector)

    def detect(
        self,
        text: str,
        enabled_types: set[PiiType] | None = None,
    ) -> list[PiiEntity]:
        candidates = []

        for detector in self._detectors:
            for entity in detector(text):
                if (
                    enabled_types is not None
                    and entity.pii_type not in enabled_types
                ):
                    continue

                candidates.append(entity)

        return resolve_overlaps(candidates)


def resolve_overlaps(
    entities: Iterable[PiiEntity],
) -> list[PiiEntity]:
    ranked = sorted(
        entities,
        key=lambda entity: (
            -entity.confidence,
            -(entity.end - entity.start),
            entity.start,
            entity.pii_type.value,
        ),
    )

    accepted = []

    for candidate in ranked:
        if any(
            candidate.overlaps(existing)
            for existing in accepted
        ):
            continue

        accepted.append(candidate)

    return sorted(
        accepted,
        key=lambda entity: (
            entity.start,
            entity.end,
            entity.pii_type.value,
        ),
    )


def build_default_registry() -> DetectorRegistry:
    from app.pii.detectors import (
        detect_bank_card,
        detect_birth_date,
        detect_cvv,
        detect_driver_license,
        detect_email,
        detect_inn,
        detect_passport_issue_date,
        detect_passport_rf,
        detect_phone,
        detect_pin,
        detect_subdivision_code,
    )

    return DetectorRegistry(
        detectors=(
            detect_email,
            detect_phone,
            detect_inn,
            detect_bank_card,
            detect_passport_rf,
            detect_subdivision_code,
            detect_birth_date,
            detect_passport_issue_date,
            detect_driver_license,
            detect_cvv,
            detect_pin,
        )
    )
