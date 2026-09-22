import unittest

from app.pii import (
    PiiType,
    build_default_registry,
)


class PiiSpanVariantTests(unittest.TestCase):
    def values_for(
        self,
        text: str,
        pii_type: PiiType,
    ) -> list[str]:
        entities = build_default_registry().detect(
            text,
            enabled_types={pii_type},
        )

        return [
            text[entity.start:entity.end]
            for entity in entities
        ]

    def test_text_birth_date_keeps_year_word_in_span(self):
        text = "Дата рождения: 15 мая 1990 года."

        self.assertEqual(
            self.values_for(
                text,
                PiiType.BIRTH_DATE,
            ),
            ["15 мая 1990 года"],
        )

    def test_text_passport_issue_date_keeps_year_word(self):
        text = "Дата выдачи паспорта: 21 августа 2015 года."

        self.assertEqual(
            self.values_for(
                text,
                PiiType.PASSPORT_ISSUE_DATE,
            ),
            ["21 августа 2015 года"],
        )

    def test_birth_place_client_label_and_period(self):
        text = "Место рождения клиента: г. Казань."

        self.assertEqual(
            self.values_for(
                text,
                PiiType.BIRTH_PLACE,
            ),
            ["г. Казань"],
        )

    def test_birth_place_narrative_period_is_outside_span(self):
        text = "Клиент родился в г. Казань."

        self.assertEqual(
            self.values_for(
                text,
                PiiType.BIRTH_PLACE,
            ),
            ["г. Казань"],
        )

    def test_birth_place_before_citizenship_keeps_both(self):
        from app.pii.models import PiiType
        from app.pii.registry import build_default_registry

        text = (
            "Место рождения: г. Казань. "
            "Гражданство: Российская Федерация."
        )

        entities = build_default_registry().detect(text)

        birth_places = [
            text[entity.start:entity.end]
            for entity in entities
            if entity.pii_type == PiiType.BIRTH_PLACE
        ]
        citizenships = [
            text[entity.start:entity.end]
            for entity in entities
            if entity.pii_type == PiiType.CITIZENSHIP
        ]

        self.assertEqual(
            birth_places,
            ["г. Казань"],
        )
        self.assertEqual(
            citizenships,
            ["Российская Федерация"],
        )

    def test_citizenship_client_label(self):
        text = (
            "Гражданство клиента: "
            "Российская Федерация."
        )

        self.assertEqual(
            self.values_for(
                text,
                PiiType.CITIZENSHIP,
            ),
            ["Российская Федерация"],
        )

    def test_passport_issued_label_can_mean_issuer(self):
        text = (
            "Паспорт выдан: "
            "ОВД района Арбат города Москвы."
        )

        self.assertEqual(
            self.values_for(
                text,
                PiiType.PASSPORT_ISSUER,
            ),
            ["ОВД района Арбат города Москвы"],
        )

    def test_passport_issuer_inline_after_number(self):
        text = (
            "Паспорт клиента: серия 45 10 номер 654321, "
            "выдан ОВД Центрального района г. Москвы, "
            "код подразделения 770-001, "
            "дата выдачи 20.04.2015."
        )

        self.assertEqual(
            self.values_for(
                text,
                PiiType.PASSPORT_ISSUER,
            ),
            ["ОВД Центрального района г. Москвы"],
        )

    def test_passport_issuer_before_subdivision_code(self):
        text = (
            "Паспорт клиента: серия 45 10 номер 654321, "
            "кем выдан: ОВД Центрального района г. Москвы, "
            "код подразделения 770-001, "
            "дата выдачи 20.04.2015."
        )

        self.assertEqual(
            self.values_for(
                text,
                PiiType.PASSPORT_ISSUER,
            ),
            ["ОВД Центрального района г. Москвы"],
        )

    def test_full_address_period_is_outside_span(self):
        text = (
            "Адрес проживания: "
            "123456, Россия, г. Москва, "
            "ул. Тверская, д. 10, кв. 5."
        )

        self.assertEqual(
            self.values_for(
                text,
                PiiType.ADDRESS,
            ),
            [
                (
                    "123456, Россия, г. Москва, "
                    "ул. Тверская, д. 10, кв. 5"
                )
            ],
        )

    def test_personal_qualified_address_components(self):
        cases = (
            (
                PiiType.COUNTRY,
                "Страна проживания клиента: Россия.",
                "Россия",
            ),
            (
                PiiType.POSTAL_CODE,
                "Индекс проживания: 123456.",
                "123456",
            ),
            (
                PiiType.CITY,
                "Город проживания клиента: Москва.",
                "Москва",
            ),
            (
                PiiType.STREET,
                "Улица проживания клиента: Тверская.",
                "Тверская",
            ),
            (
                PiiType.HOUSE,
                "Дом проживания клиента: 10.",
                "10",
            ),
            (
                PiiType.APARTMENT,
                "Квартира проживания клиента: 5.",
                "5",
            ),
        )

        for pii_type, text, expected in cases:
            with self.subTest(
                pii_type=pii_type.value,
                text=text,
            ):
                self.assertEqual(
                    self.values_for(
                        text,
                        pii_type,
                    ),
                    [expected],
                )

    def test_non_personal_address_labels_stay_negative(self):
        cases = (
            (
                PiiType.CITY,
                "Город отделения банка: Москва.",
            ),
            (
                PiiType.STREET,
                "Улица музея: Тверская.",
            ),
            (
                PiiType.HOUSE,
                "Дом офиса: 10.",
            ),
        )

        for pii_type, text in cases:
            with self.subTest(
                pii_type=pii_type.value,
                text=text,
            ):
                self.assertEqual(
                    self.values_for(
                        text,
                        pii_type,
                    ),
                    [],
                )

    def test_public_person_birth_place_stays_negative(self):
        text = "Александр Пушкин родился в Москве."

        self.assertEqual(
            self.values_for(
                text,
                PiiType.BIRTH_PLACE,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
