import re
from collections.abc import Iterable

from app.pii.models import PiiEntity, PiiType


_EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])"
    r"[A-Z0-9._%+-]+"
    r"@"
    r"[A-Z0-9.-]+"
    r"\.[A-Z]{2,63}"
    r"(?![\w.-])",
    re.IGNORECASE,
)

_PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+7|8)"
    r"[\s-]*"
    r"\(?\d{3}\)?"
    r"[\s-]*"
    r"\d{3}"
    r"[\s-]*"
    r"\d{2}"
    r"[\s-]*"
    r"\d{2}"
    r"(?!\d)",
)

_INN_PATTERN = re.compile(
    r"(?<!\d)(?:\d{12}|\d{10})(?!\d)"
)

_BANK_CARD_PATTERN = re.compile(
    r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"
)

_PASSPORT_CONTEXT_PATTERN = re.compile(
    r"(?:паспорт(?:\s+рф)?|серия)"
    r"\s*[:№N]?\s*"
    r"(?P<value>"
    r"\d{2}\s?\d{2}"
    r"\s*(?:номер|№|N)?\s*"
    r"\d{6}"
    r")"
    r"(?!\d)",
    re.IGNORECASE,
)

_PASSPORT_PLAIN_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?P<value>"
    r"(?:\d{4}\s+\d{6})"
    r"|"
    r"(?:\d{2}\s+\d{2}\s+\d{6})"
    r")"
    r"(?!\d)"
)

_SUBDIVISION_CODE_PATTERN = re.compile(
    r"\bкод\s+подразделения"
    r"\s*[:№N-]?\s*"
    r"(?P<value>\d{3}[-\s]\d{3})"
    r"(?!\d)",
    re.IGNORECASE,
)


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _valid_inn(value: str) -> bool:
    if not value.isdigit():
        return False

    digits = [int(character) for character in value]

    if len(digits) == 10:
        weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
        checksum = (
            sum(
                digit * weight
                for digit, weight in zip(digits[:9], weights)
            )
            % 11
            % 10
        )

        return checksum == digits[9]

    if len(digits) == 12:
        first_weights = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        second_weights = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)

        first_checksum = (
            sum(
                digit * weight
                for digit, weight in zip(
                    digits[:10],
                    first_weights,
                )
            )
            % 11
            % 10
        )

        if first_checksum != digits[10]:
            return False

        second_checksum = (
            sum(
                digit * weight
                for digit, weight in zip(
                    digits[:11],
                    second_weights,
                )
            )
            % 11
            % 10
        )

        return second_checksum == digits[11]

    return False


def _valid_luhn(value: str) -> bool:
    digits = [int(character) for character in value]

    if len(digits) < 13 or len(digits) > 19:
        return False

    if len(set(digits)) == 1:
        return False

    checksum = 0
    parity = len(digits) % 2

    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2

            if digit > 9:
                digit -= 9

        checksum += digit

    return checksum % 10 == 0


def detect_email(text: str) -> Iterable[PiiEntity]:
    for match in _EMAIL_PATTERN.finditer(text):
        yield PiiEntity(
            pii_type=PiiType.EMAIL,
            start=match.start(),
            end=match.end(),
            confidence=0.99,
        )


def detect_phone(text: str) -> Iterable[PiiEntity]:
    for match in _PHONE_PATTERN.finditer(text):
        normalized = _digits(match.group())

        if len(normalized) != 11:
            continue

        if normalized[0] not in {"7", "8"}:
            continue

        yield PiiEntity(
            pii_type=PiiType.PHONE,
            start=match.start(),
            end=match.end(),
            confidence=0.96,
        )


def detect_inn(text: str) -> Iterable[PiiEntity]:
    for match in _INN_PATTERN.finditer(text):
        value = match.group()

        if not _valid_inn(value):
            continue

        yield PiiEntity(
            pii_type=PiiType.INN,
            start=match.start(),
            end=match.end(),
            confidence=0.995,
        )


def detect_bank_card(text: str) -> Iterable[PiiEntity]:
    for match in _BANK_CARD_PATTERN.finditer(text):
        normalized = _digits(match.group())

        if not _valid_luhn(normalized):
            continue

        yield PiiEntity(
            pii_type=PiiType.BANK_CARD,
            start=match.start(),
            end=match.end(),
            confidence=0.995,
        )


def detect_passport_rf(text: str) -> Iterable[PiiEntity]:
    seen_spans = set()

    for pattern in (
        _PASSPORT_CONTEXT_PATTERN,
        _PASSPORT_PLAIN_PATTERN,
    ):
        for match in pattern.finditer(text):
            start, end = match.span("value")
            span = (start, end)

            if span in seen_spans:
                continue

            seen_spans.add(span)

            yield PiiEntity(
                pii_type=PiiType.PASSPORT_RF,
                start=start,
                end=end,
                confidence=0.97,
            )


def detect_subdivision_code(text: str) -> Iterable[PiiEntity]:
    for match in _SUBDIVISION_CODE_PATTERN.finditer(text):
        start, end = match.span("value")

        yield PiiEntity(
            pii_type=PiiType.SUBDIVISION_CODE,
            start=start,
            end=end,
            confidence=0.98,
        )
