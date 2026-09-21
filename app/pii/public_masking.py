import re

from app.pii.models import PiiEntity, PiiType


def _mask_fio(value: str) -> str:
    parts = re.split(r"(\s+)", value)
    masked_parts: list[str] = []

    for part in parts:
        if not part:
            continue

        if part.isspace():
            masked_parts.append(part)
            continue

        hyphen_parts = part.split("-")
        masked_hyphen_parts: list[str] = []

        for item in hyphen_parts:
            first_letter = next(
                (
                    char
                    for char in item
                    if char.isalpha()
                ),
                None,
            )

            if first_letter is None:
                masked_hyphen_parts.append(
                    "".join(
                        "*"
                        if char.isalnum()
                        else char
                        for char in item
                    )
                )
                continue

            masked_hyphen_parts.append(
                f"{first_letter}."
            )

        masked_parts.append(
            "-".join(masked_hyphen_parts)
        )

    return "".join(masked_parts)


def _mask_passport_rf(value: str) -> str:
    digit_positions = [
        index
        for index, char in enumerate(value)
        if char.isdigit()
    ]

    if len(digit_positions) < 5:
        return _mask_generic(value)

    visible_positions = set(
        digit_positions[:2]
        + digit_positions[-2:]
    )

    chars = list(value)

    for index, char in enumerate(chars):
        if (
            char.isdigit()
            and index not in visible_positions
        ):
            chars[index] = "*"

    return "".join(chars)


def _mask_generic(value: str) -> str:
    return "".join(
        "*"
        if char.isalnum()
        else char
        for char in value
    )


def mask_public_value(
    pii_type: PiiType,
    value: str,
) -> str:
    """
    Render a scorer-facing masking candidate.

    FIO and Russian passport behavior are based on the
    single published API example. Other PII types use a
    conservative shape-preserving fallback: letters and
    digits become '*', separators stay in place.
    """

    if pii_type == PiiType.FIO:
        return _mask_fio(value)

    if pii_type == PiiType.PASSPORT_RF:
        return _mask_passport_rf(value)

    return _mask_generic(value)


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
        parts.append(
            text[cursor:entity.start]
        )

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
