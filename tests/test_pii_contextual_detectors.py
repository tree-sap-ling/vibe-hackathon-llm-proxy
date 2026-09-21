import unittest

from app.pii import PiiType, build_default_registry


class PiiContextualDetectorTests(unittest.TestCase):
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

    def test_birth_date_numeric_dmy(self):
        text = "Дата рождения: 15.05.1990."

        self.assertEqual(
            self.values_for(text, PiiType.BIRTH_DATE),
            ["15.05.1990"],
        )

    def test_birth_date_numeric_mdy(self):
        text = "ДАТА РОЖДЕНИЯ 05.15.1990"

        self.assertEqual(
            self.values_for(text, PiiType.BIRTH_DATE),
            ["05.15.1990"],
        )

    def test_birth_date_year_first_day_month(self):
        text = "Родился 1990.15.05"

        self.assertEqual(
            self.values_for(text, PiiType.BIRTH_DATE),
            ["1990.15.05"],
        )

    def test_birth_date_text_month(self):
        text = "дата рождения 15 мая 1990"

        self.assertEqual(
            self.values_for(text, PiiType.BIRTH_DATE),
            ["15 мая 1990"],
        )

    def test_invalid_birth_date_is_rejected(self):
        text = "Дата рождения: 31.02.1990"

        self.assertEqual(
            self.values_for(text, PiiType.BIRTH_DATE),
            [],
        )

    def test_passport_issue_date(self):
        text = "Паспорт выдан 21-09-2020"

        self.assertEqual(
            self.values_for(
                text,
                PiiType.PASSPORT_ISSUE_DATE,
            ),
            ["21-09-2020"],
        )

    def test_driver_license_requires_context(self):
        text = (
            "Водительское удостоверение: "
            "77 77 123456; "
            "Водительское удостоверение: "
            "серия 66 66 номер 654321; "
            "а просто 88 88 654321."
        )

        self.assertEqual(
            self.values_for(
                text,
                PiiType.DRIVER_LICENSE,
            ),
            [
                "77 77 123456",
                "66 66 номер 654321",
            ],
        )

        self.assertEqual(
            self.values_for(
                text,
                PiiType.PASSPORT_RF,
            ),
            [],
        )

    def test_cvv_requires_context(self):
        text = "CVV 123; обычное число 456."

        self.assertEqual(
            self.values_for(text, PiiType.CVV),
            ["123"],
        )

    def test_cvc_and_security_code_variants(self):
        for text, expected in (
            ("cVc2: 987", "987"),
            ("КОД БЕЗОПАСНОСТИ 1234", "1234"),
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    self.values_for(text, PiiType.CVV),
                    [expected],
                )

    def test_pin_requires_context(self):
        text = (
            "ПИН-код: 4321; "
            "обычное число 1234."
        )

        self.assertEqual(
            self.values_for(text, PiiType.PIN),
            ["4321"],
        )

    def test_pin_is_case_insensitive(self):
        text = "PIN 9876"

        self.assertEqual(
            self.values_for(text, PiiType.PIN),
            ["9876"],
        )


if __name__ == "__main__":
    unittest.main()
