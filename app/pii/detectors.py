import re
from collections.abc import Iterable

from app.pii.models import PiiEntity, PiiType


_EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])"
    r"[A-Z0-9._%+-]+"
    r"@"
    r"[A-Z0-9.-]+"
    r"\.[A-Z]{2,63}"
    r"(?![\w-])",
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
    r"(?:"
    r"паспорт(?:\s+рф)?"
    r"(?:\s+(?:клиента|за[её]мщика|пользователя|пациента))?"
    r"|серия"
    r")"
    r"\s*[:№N]?\s*"
    r"(?P<value>"
    r"\d{2}\s?\d{2}"
    r"\s*(?:номер|№|N)?\s*"
    r"\d{6}"
    r")"
    r"(?!\d)",
    re.IGNORECASE,
)


_SUBDIVISION_CODE_PATTERN = re.compile(
    r"\bкод\s+подразделения"
    r"(?:\s+паспорта)?"
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


def detect_passport_rf(
    text: str,
) -> Iterable[PiiEntity]:
    for match in _PASSPORT_CONTEXT_PATTERN.finditer(text):
        prefix = text[
            max(0, match.start() - 80):match.start()
        ]

        if (
            _DRIVER_LICENSE_CONTEXT_BEFORE_SERIES_PATTERN
            .search(prefix)
        ):
            continue

        start, end = match.span("value")

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


_RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

_DATE_VALUE_PATTERN = (
    r"(?:"
    r"\d{1,2}[./-]\d{1,2}[./-]\d{4}"
    r"|"
    r"\d{4}[./-]\d{1,2}[./-]\d{1,2}"
    r"|"
    r"\d{1,2}\s+"
    r"(?:января|февраля|марта|апреля|мая|июня|июля|августа|"
    r"сентября|октября|ноября|декабря)"
    r"\s+\d{4}"
    r")"
)

_BIRTH_DATE_PATTERN = re.compile(
    r"(?:"
    r"дата\s+рождения"
    r"(?:\s+(?:клиента|за[её]мщика|пользователя|пациента))?"
    r"|родил(?:ся|ась)?"
    r")"
    r"\s*[:=-]?\s*"
    r"(?P<value>(?:\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}(?:\s+(?:года?|г\.))?))",
    re.IGNORECASE,
)

_PASSPORT_ISSUE_DATE_PATTERN = re.compile(
    r"(?:дата\s+выдачи(?:\s+паспорта)?|паспорт\s+выдан)"
    r"\s*[:=-]?\s*"
    r"(?P<value>(?:\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}(?:\s+(?:года?|г\.))?))",
    re.IGNORECASE,
)

_DRIVER_LICENSE_CONTEXT_BEFORE_SERIES_PATTERN = re.compile(
    r"(?:водительск(?:ое|ого)\s+удостоверени(?:е|я)|в\s*/\s*у|\bву\b)"
    r"\s*[:№N=-]?\s*$",
    re.IGNORECASE,
)

_DRIVER_LICENSE_PATTERN = re.compile(
    r"(?:водительск(?:ое|ого)\s+удостоверени(?:е|я)|в\s*/\s*у|\bву\b)"
    r"\s*[:№N=-]?\s*(?:серия\s*)?"
    r"(?P<value>\d{2}\s?\d{2}\s*(?:номер|№|N)?\s*\d{6})(?!\d)",
    re.IGNORECASE,
)

_CVV_PATTERN = re.compile(
    r"(?:\bcvv2?\b|\bcvc2?\b|код\s+безопасности)"
    r"(?:\s+карты)?"
    r"(?:\s+(?:клиента|за[её]мщика|пользователя))?"
    r"\s*[:=-]?\s*(?P<value>\d{3,4})(?!\d)",
    re.IGNORECASE,
)

_PIN_PATTERN = re.compile(
    r"(?:\bpin\b|пин(?:\s*|-)?код)"
    r"(?:\s+карты)?"
    r"(?:\s+(?:клиента|за[её]мщика|пользователя))?"
    r"\s*[:=-]?\s*"
    r"(?P<value>\d{4})"
    r"(?!\d)",
    re.IGNORECASE,
)


def _valid_calendar_date(value: str) -> bool:
    from datetime import date

    normalized = value.strip().lower()

    text_match = re.fullmatch(
        r"(?P<day>\d{1,2})\s+"
        r"(?P<month>[а-яё]+)\s+"
        r"(?P<year>\d{4})",
        normalized,
        re.IGNORECASE,
    )

    candidates = []

    if text_match:
        month = _RU_MONTHS.get(
            text_match.group("month")
        )

        if month is None:
            return False

        candidates.append(
            (
                int(text_match.group("year")),
                month,
                int(text_match.group("day")),
            )
        )
    else:
        parts = re.split(r"[./-]", normalized)

        if len(parts) != 3:
            return False

        first, second, third = parts

        try:
            a = int(first)
            b = int(second)
            c = int(third)
        except ValueError:
            return False

        if len(first) == 4:
            candidates.extend(
                (
                    (a, b, c),
                    (a, c, b),
                )
            )
        elif len(third) == 4:
            candidates.extend(
                (
                    (c, b, a),
                    (c, a, b),
                )
            )
        else:
            return False

    for year, month, day in candidates:
        if not 1900 <= year <= 2100:
            continue

        try:
            date(year, month, day)
        except ValueError:
            continue

        return True

    return False


def _detect_contextual_date(
    text: str,
    pattern: re.Pattern[str],
    pii_type: PiiType,
    confidence: float,
) -> Iterable[PiiEntity]:
    for match in pattern.finditer(text):
        value = match.group("value")
        validation_value = re.sub(
            r"\s+(?:года?|г\.)$",
            "",
            value,
            flags=re.IGNORECASE,
        )

        if not _valid_calendar_date(validation_value):
            continue

        start, end = match.span("value")

        yield PiiEntity(
            pii_type=pii_type,
            start=start,
            end=end,
            confidence=confidence,
        )


def detect_birth_date(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_contextual_date(
        text,
        _BIRTH_DATE_PATTERN,
        PiiType.BIRTH_DATE,
        0.98,
    )


def detect_passport_issue_date(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_contextual_date(
        text,
        _PASSPORT_ISSUE_DATE_PATTERN,
        PiiType.PASSPORT_ISSUE_DATE,
        0.98,
    )


def detect_driver_license(
    text: str,
) -> Iterable[PiiEntity]:
    for match in _DRIVER_LICENSE_PATTERN.finditer(text):
        start, end = match.span("value")

        yield PiiEntity(
            pii_type=PiiType.DRIVER_LICENSE,
            start=start,
            end=end,
            confidence=0.985,
        )


def detect_cvv(
    text: str,
) -> Iterable[PiiEntity]:
    for match in _CVV_PATTERN.finditer(text):
        start, end = match.span("value")

        yield PiiEntity(
            pii_type=PiiType.CVV,
            start=start,
            end=end,
            confidence=0.99,
        )


def detect_pin(
    text: str,
) -> Iterable[PiiEntity]:
    for match in _PIN_PATTERN.finditer(text):
        start, end = match.span("value")

        yield PiiEntity(
            pii_type=PiiType.PIN,
            start=start,
            end=end,
            confidence=0.99,
        )


_RU_NAME_WORD = (
    r"[А-ЯЁ][А-ЯЁа-яё-]{1,39}"
)
_LATIN_NAME_WORD = (
    r"[A-Z][A-Za-z'-]{1,39}"
)

_FIO_PATTERN = re.compile(
    r"(?:"
    r"\bфио\b"
    r"(?:\s+(?:клиента|за[её]мщика|пользователя|пациента))?"
    r"|"
    r"ф\.?\s*и\.?\s*о\.?"
    r"|"
    r"\bклиент\b"
    r"|"
    r"\bза[её]мщик\b"
    r")"
    r"\s*[:=-]?\s*"
    r"(?P<value>"
    + _RU_NAME_WORD
    + r"\s+"
    + _RU_NAME_WORD
    + r"(?:\s+"
    + _RU_NAME_WORD
    + r")?"
    r")",
    re.IGNORECASE,
)

_BIRTH_PLACE_PATTERN = re.compile(
    r"место\s+рождения"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r"\s*[:=-]?\s*"
    r"(?P<value>[^;\n]{2,120}?)"
    r"(?=(?:\.\s+(?=гражданство\b)|;\s*|\n|$))",
    re.IGNORECASE,
)

_BIRTH_PLACE_PERSONAL_NARRATIVE_PATTERN = re.compile(
    r"\b(?:я|клиент|заемщик|заёмщик|пользователь|пациент)\b"
    r"[^;\n]{0,80}?\bродил(?:ся|ась)\s+в\s*[:=-]?\s*"
    r"(?P<value>[^;\n]{2,120}?)(?=(?:;\s*|\n|$))",
    re.IGNORECASE,
)

_CITIZENSHIP_PATTERN = re.compile(
    r"\bгражданство\b"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r"\s*[:=-]?\s*"
    r"(?P<value>"
    r"[A-Za-zА-ЯЁа-яё]"
    r"[A-Za-zА-ЯЁа-яё .'-]{1,60}"
    r")"
    r"(?=(?:[;,\n]|$))",
    re.IGNORECASE,
)

_PASSPORT_ISSUER_PATTERN = re.compile(
    r"(?:"
    r"кем\s+выдан(?:\s+паспорт)?"
    r"|орган\s*,?\s*выдавший\s+паспорт"
    r"|орган\s+выдачи(?:\s+паспорта)?"
    r"|паспорт\s+выдан"
    r"|паспорт[^.;\n]{0,100}\bвыдан"
    r")"
    r"\s*[:=-]?\s*"
    r"(?P<value>[^;\n]{3,180}?)"
    r"(?=(?:,\s*(?=(?:код\s+подразделения|дата\s+выдачи)\b)"
    r"|;\s*|\n|$))",
    re.IGNORECASE,
)

_ADDRESS_PATTERN = re.compile(
    r"(?:"
    r"\bадрес(?:\s+(?:регистрации|проживания))?"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r"|место\s+жительства"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r")"
    r"\s*[:=-]\s*"
    r"(?P<value>[^;\n]{5,250}?)"
    r"(?=(?:;\s*|\n|$))",
    re.IGNORECASE,
)

_COUNTRY_PATTERN = re.compile(
    r"\bстрана\b"
    r"(?:\s+(?:проживания|регистрации))?"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r"\s*[:=-]\s*"
    r"(?P<value>"
    r"[A-Za-zА-ЯЁа-яё]"
    r"[A-Za-zА-ЯЁа-яё .'-]{1,60}"
    r")"
    r"(?=(?:[;,\n]|$))",
    re.IGNORECASE,
)

_POSTAL_CODE_PATTERN = re.compile(
    r"(?:\bиндекс\b|\bпочтовый\s+индекс\b)"
    r"(?:\s+(?:проживания|регистрации))?"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r"\s*[:=-]?\s*"
    r"(?P<value>\d{6})(?!\d)",
    re.IGNORECASE,
)

_CITY_PATTERN = re.compile(
    r"(?:\bгород\b|\bг\.)"
    r"(?:\s+(?:проживания|регистрации))?"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r"\s*[:=-]?\s*"
    r"(?P<value>"
    r"[А-ЯЁA-Z][А-ЯЁа-яёA-Za-z .'-]{1,80}"
    r")"
    r"(?=(?:[;,\n]|$))",
    re.IGNORECASE,
)

_STREET_PATTERN = re.compile(
    r"(?:\bулица\b|\bул\.)"
    r"(?:\s+(?:проживания|регистрации))?"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r"\s*[:=-]?\s*"
    r"(?P<value>"
    r"[А-ЯЁA-Z0-9]"
    r"[А-ЯЁа-яёA-Za-z0-9 .'-]{1,100}"
    r")"
    r"(?=(?:[;,\n]|$))",
    re.IGNORECASE,
)

_HOUSE_PATTERN = re.compile(
    r"(?:\bдом\b|\bд\.)"
    r"(?:\s+(?:проживания|регистрации))?"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r"\s*[:=-]?\s*"
    r"(?P<value>"
    r"\d+[A-Za-zА-ЯЁа-яё]?"
    r"(?:[/\\-]\d+)?"
    r"(?:\s*[A-Za-zА-ЯЁа-яё])?"
    r")"
    r"(?=(?:[;,\n ]|$|\.))",
    re.IGNORECASE,
)

_APARTMENT_PATTERN = re.compile(
    r"(?:\bквартира\b|\bкв\.)"
    r"(?:\s+(?:проживания|регистрации))?"
    r"(?:\s+(?:клиента|заемщика|заёмщика|пользователя|пациента))?"
    r"\s*[:=-]?\s*"
    r"(?P<value>\d+[A-Za-zА-ЯЁа-яё]?)(?!\d)",
    re.IGNORECASE,
)

_CARDHOLDER_NAME_PATTERN = re.compile(
    r"(?:"
    r"имя\s+держателя\s+карты"
    r"|"
    r"держатель\s+карты"
    r"|"
    r"cardholder(?:\s+name)?"
    r"|"
    r"name\s+on\s+card"
    r")"
    r"\s*[:=-]?\s*"
    r"(?P<value>(?:"
    + _RU_NAME_WORD
    + r"|"
    + _LATIN_NAME_WORD
    + r")\s+(?:"
    + _RU_NAME_WORD
    + r"|"
    + _LATIN_NAME_WORD
    + r")(?:\s+(?:"
    + _RU_NAME_WORD
    + r"|"
    + _LATIN_NAME_WORD
    + r"))?"
    r")",
    re.IGNORECASE,
)


def _detect_group_value(
    text: str,
    pattern: re.Pattern[str],
    pii_type: PiiType,
    confidence: float,
) -> Iterable[PiiEntity]:
    for match in pattern.finditer(text):
        start, end = match.span("value")

        while (
            end > start
            and text[end - 1] in " \t\r\n.,!?"
        ):
            end -= 1

        if end <= start:
            continue

        yield PiiEntity(
            pii_type=pii_type,
            start=start,
            end=end,
            confidence=confidence,
        )


def detect_fio(text: str) -> Iterable[PiiEntity]:
    yield from _detect_group_value(
        text,
        _FIO_PATTERN,
        PiiType.FIO,
        0.94,
    )


def detect_birth_place(
    text: str,
) -> Iterable[PiiEntity]:
    for pattern in (
        _BIRTH_PLACE_PATTERN,
        _BIRTH_PLACE_PERSONAL_NARRATIVE_PATTERN,
    ):
        yield from _detect_group_value(
            text,
            pattern,
            PiiType.BIRTH_PLACE,
            0.96,
        )


def detect_citizenship(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_group_value(
        text,
        _CITIZENSHIP_PATTERN,
        PiiType.CITIZENSHIP,
        0.97,
    )


def detect_passport_issuer(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_group_value(
        text,
        _PASSPORT_ISSUER_PATTERN,
        PiiType.PASSPORT_ISSUER,
        0.97,
    )


def detect_address(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_group_value(
        text,
        _ADDRESS_PATTERN,
        PiiType.ADDRESS,
        0.96,
    )


def detect_country(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_group_value(
        text,
        _COUNTRY_PATTERN,
        PiiType.COUNTRY,
        0.96,
    )


def detect_postal_code(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_address_component(
        text,
        _POSTAL_CODE_PATTERN,
        PiiType.POSTAL_CODE,
        0.98,
    )


def _is_inside_personal_address(
    text: str,
    start: int,
    end: int,
) -> bool:
    for address_match in _ADDRESS_PATTERN.finditer(text):
        address_start, address_end = address_match.span(
            "value"
        )

        if (
            address_start <= start
            and end <= address_end
        ):
            return True

    return False


def _component_context_allowed(
    text: str,
    match: re.Match[str],
) -> bool:
    value_start, value_end = match.span("value")

    label_and_separator = text[
        match.start():value_start
    ]

    if any(
        separator in label_and_separator
        for separator in (":", "=", "-")
    ):
        return True

    return _is_inside_personal_address(
        text,
        value_start,
        value_end,
    )


def _detect_address_component(
    text: str,
    pattern: re.Pattern[str],
    pii_type: PiiType,
    confidence: float,
) -> Iterable[PiiEntity]:
    for match in pattern.finditer(text):
        if not _component_context_allowed(
            text,
            match,
        ):
            continue

        start, end = match.span("value")

        while (
            end > start
            and text[end - 1] in " \t\r\n.,!?"
        ):
            end -= 1

        if end <= start:
            continue

        yield PiiEntity(
            pii_type=pii_type,
            start=start,
            end=end,
            confidence=confidence,
        )


def detect_city(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_address_component(
        text,
        _CITY_PATTERN,
        PiiType.CITY,
        0.94,
    )


def detect_street(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_address_component(
        text,
        _STREET_PATTERN,
        PiiType.STREET,
        0.94,
    )


def detect_house(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_address_component(
        text,
        _HOUSE_PATTERN,
        PiiType.HOUSE,
        0.95,
    )


def detect_apartment(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_address_component(
        text,
        _APARTMENT_PATTERN,
        PiiType.APARTMENT,
        0.95,
    )


def detect_cardholder_name(
    text: str,
) -> Iterable[PiiEntity]:
    yield from _detect_group_value(
        text,
        _CARDHOLDER_NAME_PATTERN,
        PiiType.CARDHOLDER_NAME,
        0.97,
    )
