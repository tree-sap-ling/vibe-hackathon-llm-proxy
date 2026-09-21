import unittest

from app.pii import PiiType, build_default_registry


class PiiIdentityAddressTests(unittest.TestCase):
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

    def test_fio_with_explicit_label(self):
        text = "ФИО: Иванов Иван Иванович"

        self.assertEqual(
            self.values_for(text, PiiType.FIO),
            ["Иванов Иван Иванович"],
        )

    def test_client_name_is_detected(self):
        text = "Клиент Петров Пётр Петрович"

        self.assertEqual(
            self.values_for(text, PiiType.FIO),
            ["Петров Пётр Петрович"],
        )

    def test_public_person_without_personal_context_is_not_fio(self):
        text = "Поэт Александр Пушкин написал стихотворение."

        self.assertEqual(
            self.values_for(text, PiiType.FIO),
            [],
        )

    def test_birth_place_requires_context(self):
        text = "Место рождения: г. Казань, Республика Татарстан"

        self.assertEqual(
            self.values_for(
                text,
                PiiType.BIRTH_PLACE,
            ),
            ["г. Казань, Республика Татарстан"],
        )

    def test_citizenship(self):
        text = "ГРАЖДАНСТВО: Российская Федерация"

        self.assertEqual(
            self.values_for(
                text,
                PiiType.CITIZENSHIP,
            ),
            ["Российская Федерация"],
        )

    def test_passport_issuer(self):
        text = (
            "Кем выдан паспорт: "
            "ГУ МВД России по г. Москве"
        )

        self.assertEqual(
            self.values_for(
                text,
                PiiType.PASSPORT_ISSUER,
            ),
            ["ГУ МВД России по г. Москве"],
        )

    def test_full_address(self):
        text = (
            "Адрес проживания: "
            "123456, Россия, г. Москва, "
            "ул. Тверская, д. 10, кв. 5"
        )

        self.assertEqual(
            self.values_for(
                text,
                PiiType.ADDRESS,
            ),
            [
                "123456, Россия, г. Москва, "
                "ул. Тверская, д. 10, кв. 5"
            ],
        )

    def test_separate_address_components(self):
        cases = (
            (
                "Страна: Россия",
                PiiType.COUNTRY,
                "Россия",
            ),
            (
                "Индекс: 123456",
                PiiType.POSTAL_CODE,
                "123456",
            ),
            (
                "Город: Москва",
                PiiType.CITY,
                "Москва",
            ),
            (
                "Улица: Большая Дмитровка",
                PiiType.STREET,
                "Большая Дмитровка",
            ),
            (
                "Дом: 10А",
                PiiType.HOUSE,
                "10А",
            ),
            (
                "Квартира: 25",
                PiiType.APARTMENT,
                "25",
            ),
        )

        for text, pii_type, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(
                    self.values_for(
                        text,
                        pii_type,
                    ),
                    [expected],
                )

    def test_cardholder_name_cyrillic(self):
        text = "Имя держателя карты: Иван Иванов"

        self.assertEqual(
            self.values_for(
                text,
                PiiType.CARDHOLDER_NAME,
            ),
            ["Иван Иванов"],
        )

    def test_cardholder_name_latin(self):
        text = "CARDHOLDER NAME: IVAN IVANOV"

        self.assertEqual(
            self.values_for(
                text,
                PiiType.CARDHOLDER_NAME,
            ),
            ["IVAN IVANOV"],
        )

    def test_address_of_bank_without_personal_label_is_not_detected(self):
        texts = (
            (
                "Отделение банка находится: "
                "Москва, Тверская 10."
            ),
            (
                "Адрес отделения банка: "
                "г. Москва, ул. Тверская, д. 10"
            ),
            (
                "Адрес музея: "
                "г. Москва, ул. Волхонка, д. 12"
            ),
        )

        for text in texts:
            with self.subTest(text=text):
                for pii_type in (
                    PiiType.ADDRESS,
                    PiiType.CITY,
                    PiiType.STREET,
                    PiiType.HOUSE,
                    PiiType.APARTMENT,
                    PiiType.POSTAL_CODE,
                ):
                    self.assertEqual(
                        self.values_for(
                            text,
                            pii_type,
                        ),
                        [],
                    )


    def test_birth_place_narrative_requires_personal_context(self):
        historical_text = (
            "Александр Пушкин родился в Москве."
        )
        personal_text = (
            "Клиент Александр Иванов "
            "родился в Омске."
        )

        self.assertEqual(
            self.values_for(
                historical_text,
                PiiType.BIRTH_PLACE,
            ),
            [],
        )

        self.assertEqual(
            self.values_for(
                personal_text,
                PiiType.BIRTH_PLACE,
            ),
            ["Омске."],
        )

    def test_inline_components_require_personal_address_context(self):
        text = (
            "Адрес проживания: "
            "г. Москва, ул. Тверская, "
            "д. 10, кв. 5"
        )

        cases = (
            (
                PiiType.CITY,
                "Москва",
            ),
            (
                PiiType.STREET,
                "Тверская",
            ),
            (
                PiiType.HOUSE,
                "10",
            ),
            (
                PiiType.APARTMENT,
                "5",
            ),
        )

        for pii_type, expected in cases:
            with self.subTest(
                pii_type=pii_type
            ):
                self.assertEqual(
                    self.values_for(
                        text,
                        pii_type,
                    ),
                    [expected],
                )


if __name__ == "__main__":
    unittest.main()
