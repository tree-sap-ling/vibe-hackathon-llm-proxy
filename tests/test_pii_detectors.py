import unittest

from app.pii import (
    DetectorRegistry,
    PiiEntity,
    PiiType,
    build_default_registry,
)
from app.pii.detectors import (
    detect_bank_card,
    detect_inn,
    detect_passport_rf,
    detect_subdivision_code,
)


def make_inn10(prefix: str) -> str:
    if len(prefix) != 9 or not prefix.isdigit():
        raise ValueError("prefix must contain exactly 9 digits")

    digits = [int(character) for character in prefix]
    weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)

    checksum = (
        sum(
            digit * weight
            for digit, weight in zip(digits, weights)
        )
        % 11
        % 10
    )

    return prefix + str(checksum)


def make_inn12(prefix: str) -> str:
    if len(prefix) != 10 or not prefix.isdigit():
        raise ValueError("prefix must contain exactly 10 digits")

    digits = [int(character) for character in prefix]

    first_weights = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    first_checksum = (
        sum(
            digit * weight
            for digit, weight in zip(
                digits,
                first_weights,
            )
        )
        % 11
        % 10
    )

    digits.append(first_checksum)

    second_weights = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    second_checksum = (
        sum(
            digit * weight
            for digit, weight in zip(
                digits,
                second_weights,
            )
        )
        % 11
        % 10
    )

    digits.append(second_checksum)

    return "".join(str(digit) for digit in digits)


class PiiDetectorTests(unittest.TestCase):
    def test_default_registry_detects_email_and_phone(self):
        text = (
            "Свяжитесь: TEST.User+demo@example.com, "
            "телефон +7 (999) 123-45-67."
        )

        entities = build_default_registry().detect(text)

        detected = {
            (
                entity.pii_type,
                text[entity.start:entity.end],
            )
            for entity in entities
        }

        self.assertIn(
            (
                PiiType.EMAIL,
                "TEST.User+demo@example.com",
            ),
            detected,
        )
        self.assertIn(
            (
                PiiType.PHONE,
                "+7 (999) 123-45-67",
            ),
            detected,
        )

    def test_email_before_sentence_period_is_detected(self):
        text = "Напишите на user@example.com."

        entities = build_default_registry().detect(text)

        values = [
            text[entity.start:entity.end]
            for entity in entities
            if entity.pii_type == PiiType.EMAIL
        ]

        self.assertEqual(values, ["user@example.com"])

    def test_detects_valid_ten_and_twelve_digit_inn(self):
        inn10 = make_inn10("123456789")
        inn12 = make_inn12("1234567890")

        text = f"ИНН {inn10}; второй ИНН {inn12}"

        values = [
            text[entity.start:entity.end]
            for entity in detect_inn(text)
        ]

        self.assertEqual(values, [inn10, inn12])

    def test_inn_checksum_rejects_invalid_number(self):
        entities = list(
            detect_inn(
                "ИНН 1234567890 и ИНН 123456789012"
            )
        )

        self.assertEqual(entities, [])

    def test_bank_card_uses_luhn_validation(self):
        text = (
            "Тестовая карта 4111 1111 1111 1111, "
            "невалидная 4111 1111 1111 1112."
        )

        values = [
            text[entity.start:entity.end]
            for entity in detect_bank_card(text)
        ]

        self.assertEqual(
            values,
            ["4111 1111 1111 1111"],
        )

    def test_passport_supports_common_variants_and_case(self):
        text = (
            "ПАСПОРТ 4510123456; "
            "серия 45 10 номер 654321; "
            "ещё 4510 111222 без контекста; "
            "Водительское удостоверение: "
            "серия 77 77 номер 123456."
        )

        values = [
            text[entity.start:entity.end]
            for entity in detect_passport_rf(text)
        ]

        self.assertEqual(
            values,
            [
                "4510123456",
                "45 10 номер 654321",
            ],
        )

    def test_passport_accepts_consumer_qualifier(self):
        text = "Паспорт клиента: 4509 123456."

        values = [
            text[entity.start:entity.end]
            for entity in detect_passport_rf(text)
        ]

        self.assertEqual(values, ["4509 123456"])

    def test_subdivision_code_requires_context(self):
        text = (
            "КОД ПОДРАЗДЕЛЕНИЯ: 770-001; "
            "а просто 123-456 без подписи."
        )

        values = [
            text[entity.start:entity.end]
            for entity in detect_subdivision_code(text)
        ]

        self.assertEqual(values, ["770-001"])

    def test_subdivision_code_accepts_passport_qualifier(self):
        text = "Код подразделения паспорта: 770-001."

        values = [
            text[entity.start:entity.end]
            for entity in detect_subdivision_code(text)
        ]

        self.assertEqual(values, ["770-001"])

    def test_registry_filters_enabled_types(self):
        text = (
            "Email user@example.com, "
            "телефон 8 999 123 45 67."
        )

        entities = build_default_registry().detect(
            text,
            enabled_types={PiiType.EMAIL},
        )

        self.assertEqual(len(entities), 1)
        self.assertEqual(
            entities[0].pii_type,
            PiiType.EMAIL,
        )

    def test_registry_resolves_overlaps_by_confidence(self):
        def low_confidence_detector(text):
            yield PiiEntity(
                pii_type=PiiType.PHONE,
                start=0,
                end=5,
                confidence=0.50,
            )

        def high_confidence_detector(text):
            yield PiiEntity(
                pii_type=PiiType.EMAIL,
                start=0,
                end=10,
                confidence=0.99,
            )

        registry = DetectorRegistry(
            detectors=(
                low_confidence_detector,
                high_confidence_detector,
            )
        )

        entities = registry.detect("abcdefghij")

        self.assertEqual(
            entities,
            [
                PiiEntity(
                    pii_type=PiiType.EMAIL,
                    start=0,
                    end=10,
                    confidence=0.99,
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
