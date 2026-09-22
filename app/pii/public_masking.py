import re

from app.pii.models import PiiEntity, PiiType


_YEAR_SERVICE_PATTERNS = (
    re.compile(r"\b(?:год|года)\b", re.IGNORECASE),
    re.compile(r"(?<!\w)г\.(?=\s|$)", re.IGNORECASE),
)

_DOCUMENT_SERVICE_PATTERNS = (
    re.compile(r"\b(?:серия|номер)\b", re.IGNORECASE),
    re.compile(r"(?<!\w)[Nn](?=\s*\d)"),
)

_PLACE_SERVICE_PATTERNS = (
    re.compile(r"(?<!\w)г\.(?=\s|$)", re.IGNORECASE),
    re.compile(
        r"\b(?:город|республика|область|край|район)\b",
        re.IGNORECASE,
    ),
)

_ADDRESS_SERVICE_PATTERNS = (
    re.compile(
        r"(?<!\w)(?:г|ул|д|кв|корп|стр|обл|пер|наб|ш)"
        r"\.(?=\s|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<!\w)(?:р-н|пр-т)(?=\s|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:"
        r"город|улица|дом|квартира|корпус|строение|"
        r"область|район|республика|край|"
        r"проспект|переулок|набережная|шоссе"
        r")\b",
        re.IGNORECASE,
    ),
)

_SERVICE_PATTERNS_BY_TYPE = {
    PiiType.PASSPORT_RF: _DOCUMENT_SERVICE_PATTERNS,
    PiiType.DRIVER_LICENSE: _DOCUMENT_SERVICE_PATTERNS,
    PiiType.BIRTH_DATE: _YEAR_SERVICE_PATTERNS,
    PiiType.PASSPORT_ISSUE_DATE: _YEAR_SERVICE_PATTERNS,
    PiiType.BIRTH_PLACE: _PLACE_SERVICE_PATTERNS,
    PiiType.ADDRESS: _ADDRESS_SERVICE_PATTERNS,
}


def _preserved_positions(
    value: str,
    patterns: tuple[re.Pattern[str], ...],
) -> set[int]:
    preserved: set[int] = set()

    for pattern in patterns:
        for match in pattern.finditer(value):
            preserved.update(
                range(match.start(), match.end())
            )

    return preserved


def _mask_generic(
    value: str,
    *,
    preserved_patterns: tuple[
        re.Pattern[str],
        ...,
    ] = (),
) -> str:
    preserved = _preserved_positions(
        value,
        preserved_patterns,
    )

    return "".join(
        char
        if index in preserved or not char.isalnum()
        else "*"
        for index, char in enumerate(value)
    )


def mask_public_value(
    pii_type: PiiType,
    value: str,
) -> str:
    """
    Fully hide PII alphanumeric characters while keeping
    separators and known structural/service markers readable.

    Exact restoration uses the internal request-local vault
    and does not depend on this scorer-facing representation.
    """

    return _mask_generic(
        value,
        preserved_patterns=_SERVICE_PATTERNS_BY_TYPE.get(
            pii_type,
            (),
        ),
    )


def render_public_mask(
    text: str,
    entities: list[PiiEntity],
) -> str:
    ordered = sorted(
        entities,
        key=lambda entity: (
            entity.start,
            entity.end,
            entity.pii_type.value,
        ),
    )

    previous_end = 0

    for entity in ordered:
        if entity.start < previous_end:
            raise ValueError(
                "render_public_mask requires "
                "non-overlapping entities"
            )

        if entity.end > len(text):
            raise ValueError(
                "entity span is outside source text"
            )

        previous_end = entity.end

    parts: list[str] = []
    cursor = 0

    for entity in ordered:
        parts.append(text[cursor:entity.start])

        original_value = text[
            entity.start:entity.end
        ]

        parts.append(
            mask_public_value(
                entity.pii_type,
                original_value,
            )
        )

        cursor = entity.end

    parts.append(text[cursor:])

    return "".join(parts)
