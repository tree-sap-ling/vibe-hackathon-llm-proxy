from dataclasses import dataclass

from app.pii import (
    PiiType,
    build_default_registry,
)


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    text: str
    expected: frozenset[PiiType]


CASES = (
    # EMAIL
    Case(
        "email_uppercase",
        "EMAIL: USER.NAME+TAG@EXAMPLE.COM",
        frozenset({PiiType.EMAIL}),
    ),
    Case(
        "email_trailing_comma",
        "Связь: user@example.com, следующий контакт позже.",
        frozenset({PiiType.EMAIL}),
    ),
    Case(
        "email_invalid_double_at",
        "Технический идентификатор: user@@example.com",
        frozenset(),
    ),

    # PHONE
    Case(
        "phone_parentheses",
        "Телефон: +7 (999) 123-45-67",
        frozenset({PiiType.PHONE}),
    ),
    Case(
        "phone_spaces",
        "Телефон клиента 8 999 123 45 67",
        frozenset({PiiType.PHONE}),
    ),
    Case(
        "phone_short_negative",
        "Код подтверждения 123456",
        frozenset(),
    ),

    # INN
    Case(
        "inn_context_valid",
        "ИНН: 7707083893",
        frozenset({PiiType.INN}),
    ),
    Case(
        "inn_invalid_checksum_negative",
        "ИНН: 7707083894",
        frozenset(),
    ),

    # BANK CARD
    Case(
        "card_hyphenated",
        "Номер карты: 4111-1111-1111-1111",
        frozenset({PiiType.BANK_CARD}),
    ),
    Case(
        "card_contiguous",
        "Карта 4111111111111111",
        frozenset({PiiType.BANK_CARD}),
    ),
    Case(
        "card_repeated_digits_negative",
        "Ссылка на тест: 0000000000000000",
        frozenset(),
    ),

    # PASSPORT
    Case(
        "passport_series_number_words",
        "Паспорт: серия 45 10 номер 123456",
        frozenset({PiiType.PASSPORT_RF}),
    ),
    Case(
        "passport_uppercase_context",
        "ПАСПОРТ 4510 123456",
        frozenset({PiiType.PASSPORT_RF}),
    ),
    Case(
        "passport_random_digits_negative",
        "Номер заявки 4510 123456",
        frozenset(),
    ),
    Case(
        "subdivision_code_spaces",
        "КОД ПОДРАЗДЕЛЕНИЯ 770 001",
        frozenset({PiiType.SUBDIVISION_CODE}),
    ),
    Case(
        "subdivision_without_context_negative",
        "Версия 770-001 опубликована.",
        frozenset(),
    ),

    # DATES
    Case(
        "birth_date_slashes",
        "Дата рождения: 15/05/1990",
        frozenset({PiiType.BIRTH_DATE}),
    ),
    Case(
        "birth_date_us_order",
        "Дата рождения: 05.15.1990",
        frozenset({PiiType.BIRTH_DATE}),
    ),
    Case(
        "birth_date_iso",
        "Дата рождения: 1990-05-15",
        frozenset({PiiType.BIRTH_DATE}),
    ),
    Case(
        "birth_date_year_day_month",
        "Дата рождения: 1990.15.05",
        frozenset({PiiType.BIRTH_DATE}),
    ),
    Case(
        "birth_date_upper_month",
        "ДАТА РОЖДЕНИЯ: 15 МАЯ 1990",
        frozenset({PiiType.BIRTH_DATE}),
    ),
    Case(
        "ordinary_date_negative",
        "Релиз версии состоялся 15.05.1990.",
        frozenset(),
    ),
    Case(
        "passport_issue_date_words",
        "Дата выдачи паспорта: 21 сентября 2020",
        frozenset({PiiType.PASSPORT_ISSUE_DATE}),
    ),

    # DRIVER LICENSE
    Case(
        "driver_license_series_number_words",
        "Водительское удостоверение: серия 77 77 номер 123456",
        frozenset({PiiType.DRIVER_LICENSE}),
    ),
    Case(
        "driver_license_random_digits_negative",
        "Артикул товара 77 77 123456",
        frozenset(),
    ),

    # CVV / PIN
    Case(
        "cvc_lowercase",
        "cvc: 123",
        frozenset({PiiType.CVV}),
    ),
    Case(
        "security_code_context",
        "Код безопасности карты: 987",
        frozenset({PiiType.CVV}),
    ),
    Case(
        "three_digits_negative",
        "HTTP status: 404",
        frozenset(),
    ),
    Case(
        "pin_lowercase",
        "pin 4321",
        frozenset({PiiType.PIN}),
    ),
    Case(
        "four_digits_negative",
        "Год основания: 4321",
        frozenset(),
    ),

    # FIO
    Case(
        "fio_lowercase_label",
        "фио: Иванов Иван Иванович",
        frozenset({PiiType.FIO}),
    ),
    Case(
        "fio_borrower_context",
        "Заемщик: Петров Пётр Петрович",
        frozenset({PiiType.FIO}),
    ),
    Case(
        "historical_person_negative",
        "Александр Пушкин родился в Москве.",
        frozenset(),
    ),
    Case(
        "fictional_reference_negative",
        "В тексте упомянут Иван Иванович Иванов как пример.",
        frozenset(),
    ),

    # BIRTH PLACE / CITIZENSHIP / ISSUER
    Case(
        "birth_place_case_insensitive",
        "МЕСТО РОЖДЕНИЯ: г. Омск",
        frozenset({PiiType.BIRTH_PLACE}),
    ),
    Case(
        "birth_place_geography_negative",
        "Город Омск расположен в России.",
        frozenset(),
    ),
    Case(
        "citizenship_case_insensitive",
        "ГРАЖДАНСТВО: РФ",
        frozenset({PiiType.CITIZENSHIP}),
    ),
    Case(
        "country_statement_negative",
        "Россия — страна в Евразии.",
        frozenset(),
    ),
    Case(
        "passport_issuer_case_insensitive",
        "КЕМ ВЫДАН ПАСПОРТ: ОВД района Арбат",
        frozenset({PiiType.PASSPORT_ISSUER}),
    ),
    Case(
        "organization_name_negative",
        "ОВД района Арбат открыло приём граждан.",
        frozenset(),
    ),

    # ADDRESS
    Case(
        "address_residence",
        "Место жительства: Россия, г. Казань, ул. Баумана, д. 1",
        frozenset({PiiType.ADDRESS}),
    ),
    Case(
        "address_uppercase",
        "АДРЕС ПРОЖИВАНИЯ: г. Москва, ул. Тверская, д. 10",
        frozenset({PiiType.ADDRESS}),
    ),
    Case(
        "branch_address_negative",
        "Адрес отделения банка: г. Москва, ул. Тверская, д. 10",
        frozenset(),
    ),
    Case(
        "museum_address_negative",
        "Адрес музея: г. Москва, ул. Волхонка, д. 12",
        frozenset(),
    ),

    # ADDRESS COMPONENTS
    Case(
        "country_uppercase",
        "СТРАНА: Россия",
        frozenset({PiiType.COUNTRY}),
    ),
    Case(
        "postal_index_spaces",
        "Почтовый индекс: 123456",
        frozenset({PiiType.POSTAL_CODE}),
    ),
    Case(
        "city_label_case",
        "ГОРОД: Казань",
        frozenset({PiiType.CITY}),
    ),
    Case(
        "street_label_case",
        "УЛИЦА: Баумана",
        frozenset({PiiType.STREET}),
    ),
    Case(
        "house_label_short",
        "д.: 10А",
        frozenset({PiiType.HOUSE}),
    ),
    Case(
        "apartment_label_short",
        "кв.: 25",
        frozenset({PiiType.APARTMENT}),
    ),

    # CARDHOLDER
    Case(
        "cardholder_mixed_case",
        "Cardholder Name: IVAN IVANOV",
        frozenset({PiiType.CARDHOLDER_NAME}),
    ),
    Case(
        "ordinary_name_negative",
        "Автор книги: IVAN IVANOV",
        frozenset(),
    ),

    # MIXED
    Case(
        "mixed_three_types",
        (
            "Клиент Иванов Иван Иванович; "
            "email user@example.com; "
            "телефон +7 (999) 123-45-67"
        ),
        frozenset({
            PiiType.FIO,
            PiiType.EMAIL,
            PiiType.PHONE,
        }),
    ),
)


def values(items):
    return sorted(item.value for item in items)


def main() -> None:
    registry = build_default_registry()

    tp = 0
    fp = 0
    fn = 0
    passed = 0
    failed_names = []

    print("PII adversarial quality check")
    print(f"cases={len(CASES)}")

    for case in CASES:
        entities = registry.detect(case.text)

        actual = {
            entity.pii_type
            for entity in entities
        }
        expected = set(case.expected)

        extra = actual - expected
        missing = expected - actual

        tp += len(actual & expected)
        fp += len(extra)
        fn += len(missing)

        if not extra and not missing:
            passed += 1
            status = "PASS"
        else:
            failed_names.append(case.name)
            status = "FAIL"

        print(
            f"{status} {case.name}: "
            f"expected={values(expected)} "
            f"actual={values(actual)}"
        )

    precision = (
        tp / (tp + fp)
        if tp + fp
        else 1.0
    )
    recall = (
        tp / (tp + fn)
        if tp + fn
        else 1.0
    )
    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )
    case_accuracy = passed / len(CASES)

    print()
    print("=== summary ===")
    print(
        f"case_accuracy={case_accuracy:.2%} "
        f"({passed}/{len(CASES)})"
    )
    print(f"type_precision={precision:.2%}")
    print(f"type_recall={recall:.2%}")
    print(f"type_f1={f1:.2%}")
    print(f"tp={tp} fp={fp} fn={fn}")

    if failed_names:
        print(
            "failed_cases="
            + ",".join(failed_names)
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
