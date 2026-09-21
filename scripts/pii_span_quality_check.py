from __future__ import annotations

from dataclasses import dataclass

from app.pii import (
    PiiType,
    build_default_registry,
)


@dataclass(frozen=True, slots=True)
class ExpectedSpan:
    pii_type: PiiType
    value: str
    occurrence: int = 1


@dataclass(frozen=True, slots=True)
class SpanCase:
    name: str
    text: str
    expected: tuple[ExpectedSpan, ...]


CASES = (
    SpanCase(
        name="official_example_fio_passport",
        text=(
            "Клиент Иванов Иван Иванович, "
            "паспорт 4509 123456"
        ),
        expected=(
            ExpectedSpan(
                PiiType.FIO,
                "Иванов Иван Иванович",
            ),
            ExpectedSpan(
                PiiType.PASSPORT_RF,
                "4509 123456",
            ),
        ),
    ),
    SpanCase(
        name="email_sentence_period",
        text="Email: user@example.com.",
        expected=(
            ExpectedSpan(
                PiiType.EMAIL,
                "user@example.com",
            ),
        ),
    ),
    SpanCase(
        name="phone_formatted",
        text="Телефон клиента: +7 (999) 123-45-67.",
        expected=(
            ExpectedSpan(
                PiiType.PHONE,
                "+7 (999) 123-45-67",
            ),
        ),
    ),
    SpanCase(
        name="inn",
        text="ИНН клиента: 7707083893.",
        expected=(
            ExpectedSpan(
                PiiType.INN,
                "7707083893",
            ),
        ),
    ),
    SpanCase(
        name="bank_card",
        text="Номер карты: 4111 1111 1111 1111.",
        expected=(
            ExpectedSpan(
                PiiType.BANK_CARD,
                "4111 1111 1111 1111",
            ),
        ),
    ),
    SpanCase(
        name="subdivision_code",
        text="Код подразделения: 770-001.",
        expected=(
            ExpectedSpan(
                PiiType.SUBDIVISION_CODE,
                "770-001",
            ),
        ),
    ),
    SpanCase(
        name="birth_date_numeric",
        text="Дата рождения: 15.05.1990.",
        expected=(
            ExpectedSpan(
                PiiType.BIRTH_DATE,
                "15.05.1990",
            ),
        ),
    ),
    SpanCase(
        name="birth_date_words",
        text="Дата рождения: 15 мая 1990 года.",
        expected=(
            ExpectedSpan(
                PiiType.BIRTH_DATE,
                "15 мая 1990 года",
            ),
        ),
    ),
    SpanCase(
        name="passport_issue_date",
        text="Паспорт выдан 21.08.2015.",
        expected=(
            ExpectedSpan(
                PiiType.PASSPORT_ISSUE_DATE,
                "21.08.2015",
            ),
        ),
    ),
    SpanCase(
        name="driver_license",
        text=(
            "Водительское удостоверение: "
            "серия 77 77 номер 654321."
        ),
        expected=(
            ExpectedSpan(
                PiiType.DRIVER_LICENSE,
                "77 77 номер 654321",
            ),
        ),
    ),
    SpanCase(
        name="cvv",
        text="CVV: 987.",
        expected=(
            ExpectedSpan(
                PiiType.CVV,
                "987",
            ),
        ),
    ),
    SpanCase(
        name="pin",
        text="ПИН-код: 4321.",
        expected=(
            ExpectedSpan(
                PiiType.PIN,
                "4321",
            ),
        ),
    ),
    SpanCase(
        name="fio_explicit_label",
        text="ФИО: Петров Петр Петрович.",
        expected=(
            ExpectedSpan(
                PiiType.FIO,
                "Петров Петр Петрович",
            ),
        ),
    ),
    SpanCase(
        name="birth_place",
        text="Место рождения клиента: г. Казань.",
        expected=(
            ExpectedSpan(
                PiiType.BIRTH_PLACE,
                "г. Казань",
            ),
        ),
    ),
    SpanCase(
        name="citizenship",
        text="Гражданство клиента: Российская Федерация.",
        expected=(
            ExpectedSpan(
                PiiType.CITIZENSHIP,
                "Российская Федерация",
            ),
        ),
    ),
    SpanCase(
        name="passport_issuer",
        text=(
            "Паспорт выдан: ОВД района Арбат "
            "города Москвы."
        ),
        expected=(
            ExpectedSpan(
                PiiType.PASSPORT_ISSUER,
                "ОВД района Арбат города Москвы",
            ),
        ),
    ),
    SpanCase(
        name="personal_full_address",
        text=(
            "Адрес проживания: "
            "123456, Россия, г. Москва, "
            "ул. Тверская, д. 10, кв. 5."
        ),
        expected=(
            ExpectedSpan(
                PiiType.ADDRESS,
                (
                    "123456, Россия, г. Москва, "
                    "ул. Тверская, д. 10, кв. 5"
                ),
            ),
        ),
    ),
    SpanCase(
        name="country_component",
        text="Страна проживания клиента: Россия.",
        expected=(
            ExpectedSpan(
                PiiType.COUNTRY,
                "Россия",
            ),
        ),
    ),
    SpanCase(
        name="postal_code_component",
        text="Индекс проживания: 123456.",
        expected=(
            ExpectedSpan(
                PiiType.POSTAL_CODE,
                "123456",
            ),
        ),
    ),
    SpanCase(
        name="city_component",
        text="Город проживания клиента: Москва.",
        expected=(
            ExpectedSpan(
                PiiType.CITY,
                "Москва",
            ),
        ),
    ),
    SpanCase(
        name="street_component",
        text="Улица проживания клиента: Тверская.",
        expected=(
            ExpectedSpan(
                PiiType.STREET,
                "Тверская",
            ),
        ),
    ),
    SpanCase(
        name="house_component",
        text="Дом проживания клиента: 10.",
        expected=(
            ExpectedSpan(
                PiiType.HOUSE,
                "10",
            ),
        ),
    ),
    SpanCase(
        name="apartment_component",
        text="Квартира проживания клиента: 5.",
        expected=(
            ExpectedSpan(
                PiiType.APARTMENT,
                "5",
            ),
        ),
    ),
    SpanCase(
        name="cardholder_name",
        text="Cardholder Name: IVAN IVANOV.",
        expected=(
            ExpectedSpan(
                PiiType.CARDHOLDER_NAME,
                "IVAN IVANOV",
            ),
        ),
    ),
    SpanCase(
        name="repeated_email_exact_positions",
        text=(
            "Email: user@example.com; "
            "повторный email: user@example.com."
        ),
        expected=(
            ExpectedSpan(
                PiiType.EMAIL,
                "user@example.com",
                occurrence=1,
            ),
            ExpectedSpan(
                PiiType.EMAIL,
                "user@example.com",
                occurrence=2,
            ),
        ),
    ),
    SpanCase(
        name="mixed_three_entities",
        text=(
            "Клиент Иванов Иван Иванович, "
            "email ivan@example.com, "
            "телефон +7 999 123-45-67."
        ),
        expected=(
            ExpectedSpan(
                PiiType.FIO,
                "Иванов Иван Иванович",
            ),
            ExpectedSpan(
                PiiType.EMAIL,
                "ivan@example.com",
            ),
            ExpectedSpan(
                PiiType.PHONE,
                "+7 999 123-45-67",
            ),
        ),
    ),
    SpanCase(
        name="historical_person_negative",
        text=(
            "Александр Сергеевич Пушкин родился "
            "в Москве и является известным поэтом."
        ),
        expected=(),
    ),
    SpanCase(
        name="bank_branch_address_negative",
        text=(
            "Адрес отделения банка: "
            "г. Москва, ул. Тверская, д. 10."
        ),
        expected=(),
    ),
    SpanCase(
        name="ordinary_date_negative",
        text="Встреча состоится 15.05.2026.",
        expected=(),
    ),
    SpanCase(
        name="random_digits_negative",
        text="Код операции: 4509 123456.",
        expected=(),
    ),
)


def locate_occurrence(
    text: str,
    value: str,
    occurrence: int,
) -> tuple[int, int]:
    if occurrence < 1:
        raise ValueError(
            "occurrence must be >= 1"
        )

    start = -1
    search_from = 0

    for _ in range(occurrence):
        start = text.find(
            value,
            search_from,
        )

        if start < 0:
            raise ValueError(
                "Expected value not found: "
                f"{value!r} occurrence={occurrence}"
            )

        search_from = start + len(value)

    return start, start + len(value)


def expected_spans(
    case: SpanCase,
) -> set[tuple[PiiType, int, int]]:
    result = set()

    for expected in case.expected:
        start, end = locate_occurrence(
            case.text,
            expected.value,
            expected.occurrence,
        )

        result.add(
            (
                expected.pii_type,
                start,
                end,
            )
        )

    return result


def format_span(
    item: tuple[PiiType, int, int],
    text: str,
) -> str:
    pii_type, start, end = item

    return (
        f"{pii_type.value}"
        f"[{start}:{end}]="
        f"{text[start:end]!r}"
    )


def main() -> int:
    registry = build_default_registry()

    passed = 0
    exact_tp = 0
    total_expected = 0
    total_actual = 0
    failed_names = []

    for case in CASES:
        expected = expected_spans(case)

        actual_entities = registry.detect(
            case.text
        )

        actual = {
            (
                entity.pii_type,
                entity.start,
                entity.end,
            )
            for entity in actual_entities
        }

        missing = expected - actual
        extra = actual - expected

        total_expected += len(expected)
        total_actual += len(actual)
        exact_tp += len(
            expected & actual
        )

        ok = not missing and not extra

        if ok:
            passed += 1
            status = "PASS"
        else:
            failed_names.append(case.name)
            status = "FAIL"

        print(
            f"{status} {case.name}"
        )

        print(
            "  expected:",
            [
                format_span(
                    span,
                    case.text,
                )
                for span in sorted(
                    expected,
                    key=lambda item: (
                        item[1],
                        item[2],
                        item[0].value,
                    ),
                )
            ],
        )

        print(
            "  actual:  ",
            [
                format_span(
                    span,
                    case.text,
                )
                for span in sorted(
                    actual,
                    key=lambda item: (
                        item[1],
                        item[2],
                        item[0].value,
                    ),
                )
            ],
        )

        if missing:
            print(
                "  missing: ",
                [
                    format_span(
                        span,
                        case.text,
                    )
                    for span in sorted(
                        missing,
                        key=lambda item: (
                            item[1],
                            item[2],
                            item[0].value,
                        ),
                    )
                ],
            )

        if extra:
            print(
                "  extra:   ",
                [
                    format_span(
                        span,
                        case.text,
                    )
                    for span in sorted(
                        extra,
                        key=lambda item: (
                            item[1],
                            item[2],
                            item[0].value,
                        ),
                    )
                ],
            )

    precision = (
        exact_tp / total_actual
        if total_actual
        else 1.0
    )

    recall = (
        exact_tp / total_expected
        if total_expected
        else 1.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )

    case_accuracy = (
        passed / len(CASES)
    )

    print()
    print("=== summary ===")
    print(
        "case_exact_accuracy="
        f"{case_accuracy:.2%} "
        f"({passed}/{len(CASES)})"
    )
    print(
        "exact_span_precision="
        f"{precision:.2%}"
    )
    print(
        "exact_span_recall="
        f"{recall:.2%}"
    )
    print(
        "exact_span_f1="
        f"{f1:.2%}"
    )
    print(
        "exact_tp=",
        exact_tp,
        "actual=",
        total_actual,
        "expected=",
        total_expected,
    )
    print(
        "failed_cases=",
        ",".join(failed_names)
        if failed_names
        else "<none>",
    )

    return 0 if not failed_names else 1


if __name__ == "__main__":
    raise SystemExit(main())
