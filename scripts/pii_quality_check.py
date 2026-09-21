from dataclasses import dataclass

from app.pii import (
    PiiType,
    build_default_registry,
)


@dataclass(frozen=True, slots=True)
class QualityCase:
    name: str
    text: str
    expected_types: frozenset[PiiType]


CASES = (
    QualityCase(
        name="email_basic",
        text="Контакт: user@example.com",
        expected_types=frozenset(
            {PiiType.EMAIL}
        ),
    ),
    QualityCase(
        name="email_sentence_period",
        text="Напишите user@example.com.",
        expected_types=frozenset(
            {PiiType.EMAIL}
        ),
    ),
    QualityCase(
        name="phone_ru",
        text="Телефон клиента: +7 999 123-45-67",
        expected_types=frozenset(
            {PiiType.PHONE}
        ),
    ),
    QualityCase(
        name="card_luhn_valid",
        text="Карта: 4111 1111 1111 1111",
        expected_types=frozenset(
            {PiiType.BANK_CARD}
        ),
    ),
    QualityCase(
        name="card_luhn_invalid",
        text="Номер заказа: 4111 1111 1111 1112",
        expected_types=frozenset(),
    ),
    QualityCase(
        name="passport_rf_context",
        text="Паспорт: 45 10 123456",
        expected_types=frozenset(
            {PiiType.PASSPORT_RF}
        ),
    ),
    QualityCase(
        name="subdivision_code",
        text="Код подразделения: 770-001",
        expected_types=frozenset(
            {PiiType.SUBDIVISION_CODE}
        ),
    ),
    QualityCase(
        name="birth_date_numeric",
        text="Дата рождения: 15.05.1990",
        expected_types=frozenset(
            {PiiType.BIRTH_DATE}
        ),
    ),
    QualityCase(
        name="birth_date_words",
        text="Дата рождения: 15 мая 1990",
        expected_types=frozenset(
            {PiiType.BIRTH_DATE}
        ),
    ),
    QualityCase(
        name="birth_date_year_first",
        text="Родился 1990.15.05",
        expected_types=frozenset(
            {PiiType.BIRTH_DATE}
        ),
    ),
    QualityCase(
        name="invalid_calendar_date",
        text="Дата рождения: 31.02.1990",
        expected_types=frozenset(),
    ),
    QualityCase(
        name="passport_issue_date",
        text="Паспорт выдан 21-09-2020",
        expected_types=frozenset(
            {PiiType.PASSPORT_ISSUE_DATE}
        ),
    ),
    QualityCase(
        name="driver_license",
        text=(
            "Водительское удостоверение: "
            "77 77 123456"
        ),
        expected_types=frozenset(
            {PiiType.DRIVER_LICENSE}
        ),
    ),
    QualityCase(
        name="cvv_context",
        text="CVV: 123",
        expected_types=frozenset(
            {PiiType.CVV}
        ),
    ),
    QualityCase(
        name="cvv_plain_number_negative",
        text="Количество элементов: 123",
        expected_types=frozenset(),
    ),
    QualityCase(
        name="pin_context",
        text="ПИН-код: 4321",
        expected_types=frozenset(
            {PiiType.PIN}
        ),
    ),
    QualityCase(
        name="pin_plain_number_negative",
        text="Номер очереди: 4321",
        expected_types=frozenset(),
    ),
    QualityCase(
        name="fio_explicit",
        text="ФИО: Иванов Иван Иванович",
        expected_types=frozenset(
            {PiiType.FIO}
        ),
    ),
    QualityCase(
        name="fio_client_context",
        text="Клиент Петров Пётр Петрович",
        expected_types=frozenset(
            {PiiType.FIO}
        ),
    ),
    QualityCase(
        name="famous_person_negative",
        text=(
            "Поэт Александр Пушкин "
            "написал стихотворение."
        ),
        expected_types=frozenset(),
    ),
    QualityCase(
        name="birth_place",
        text=(
            "Место рождения: "
            "г. Казань, Республика Татарстан"
        ),
        expected_types=frozenset(
            {PiiType.BIRTH_PLACE}
        ),
    ),
    QualityCase(
        name="citizenship",
        text="Гражданство: Российская Федерация",
        expected_types=frozenset(
            {PiiType.CITIZENSHIP}
        ),
    ),
    QualityCase(
        name="passport_issuer",
        text=(
            "Кем выдан паспорт: "
            "ГУ МВД России по г. Москве"
        ),
        expected_types=frozenset(
            {PiiType.PASSPORT_ISSUER}
        ),
    ),
    QualityCase(
        name="full_address",
        text=(
            "Адрес проживания: "
            "123456, Россия, г. Москва, "
            "ул. Тверская, д. 10, кв. 5"
        ),
        expected_types=frozenset(
            {PiiType.ADDRESS}
        ),
    ),
    QualityCase(
        name="bank_branch_address_negative",
        text=(
            "Отделение банка находится: "
            "Москва, Тверская 10."
        ),
        expected_types=frozenset(),
    ),
    QualityCase(
        name="country_component",
        text="Страна: Россия",
        expected_types=frozenset(
            {PiiType.COUNTRY}
        ),
    ),
    QualityCase(
        name="postal_code_component",
        text="Индекс: 123456",
        expected_types=frozenset(
            {PiiType.POSTAL_CODE}
        ),
    ),
    QualityCase(
        name="city_component",
        text="Город: Москва",
        expected_types=frozenset(
            {PiiType.CITY}
        ),
    ),
    QualityCase(
        name="street_component",
        text="Улица: Большая Дмитровка",
        expected_types=frozenset(
            {PiiType.STREET}
        ),
    ),
    QualityCase(
        name="house_component",
        text="Дом: 10А",
        expected_types=frozenset(
            {PiiType.HOUSE}
        ),
    ),
    QualityCase(
        name="apartment_component",
        text="Квартира: 25",
        expected_types=frozenset(
            {PiiType.APARTMENT}
        ),
    ),
    QualityCase(
        name="cardholder_cyrillic",
        text="Имя держателя карты: Иван Иванов",
        expected_types=frozenset(
            {PiiType.CARDHOLDER_NAME}
        ),
    ),
    QualityCase(
        name="cardholder_latin",
        text="CARDHOLDER NAME: IVAN IVANOV",
        expected_types=frozenset(
            {PiiType.CARDHOLDER_NAME}
        ),
    ),
    QualityCase(
        name="mixed_email_phone",
        text=(
            "Связь: user@example.com, "
            "+7 999 123-45-67"
        ),
        expected_types=frozenset(
            {
                PiiType.EMAIL,
                PiiType.PHONE,
            }
        ),
    ),
)


def sorted_values(
    values: set[PiiType] | frozenset[PiiType],
) -> list[str]:
    return sorted(
        value.value
        for value in values
    )


def main() -> None:
    registry = build_default_registry()

    true_positive = 0
    false_positive = 0
    false_negative = 0
    passed_cases = 0

    print(
        "PII synthetic quality check"
    )
    print(
        f"cases={len(CASES)}"
    )

    for case in CASES:
        entities = registry.detect(
            case.text
        )

        actual_types = {
            entity.pii_type
            for entity in entities
        }

        expected = set(
            case.expected_types
        )

        extra = actual_types - expected
        missing = expected - actual_types

        true_positive += len(
            actual_types & expected
        )
        false_positive += len(extra)
        false_negative += len(missing)

        ok = not extra and not missing

        if ok:
            passed_cases += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(
            f"{status} {case.name}: "
            f"expected={sorted_values(expected)} "
            f"actual={sorted_values(actual_types)}"
        )

    precision_denominator = (
        true_positive + false_positive
    )
    recall_denominator = (
        true_positive + false_negative
    )

    precision = (
        true_positive / precision_denominator
        if precision_denominator
        else 1.0
    )
    recall = (
        true_positive / recall_denominator
        if recall_denominator
        else 1.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )

    case_accuracy = (
        passed_cases / len(CASES)
    )

    print()
    print("=== summary ===")
    print(
        f"case_accuracy={case_accuracy:.2%} "
        f"({passed_cases}/{len(CASES)})"
    )
    print(
        f"type_precision={precision:.2%}"
    )
    print(
        f"type_recall={recall:.2%}"
    )
    print(
        f"type_f1={f1:.2%}"
    )
    print(
        f"tp={true_positive} "
        f"fp={false_positive} "
        f"fn={false_negative}"
    )

    if passed_cases != len(CASES):
        raise SystemExit(
            "Synthetic quality corpus has failures."
        )


if __name__ == "__main__":
    main()
