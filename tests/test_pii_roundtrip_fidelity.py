import re
import unittest

from app.pii.models import PiiType
from app.pii.policy import (
    ConsumerPolicy,
    PolicyRegistry,
)
from app.pii.processor import PiiProcessor


_TOKEN_PATTERN = re.compile(
    r"<PII:[a-z_]+:\d+:[0-9a-f]+>"
)


class PiiRoundTripFidelityTests(unittest.TestCase):
    def build_processor(self) -> PiiProcessor:
        policy = ConsumerPolicy(
            system_id="crm",
            enabled_types=frozenset(PiiType),
            demask_enabled=True,
            enabled=True,
        )

        return PiiProcessor(
            PolicyRegistry((policy,))
        )

    def test_mixed_pii_exact_round_trip(self):
        processor = self.build_processor()

        text = (
            "ФИО: Иванов Иван Иванович; "
            "Дата рождения: 15.05.1990; "
            "Email: ivan.petrov@example.com; "
            "Телефон: +7 (999) 123-45-67; "
            "ИНН: 7707083893; "
            "Паспорт 4510 123456; "
            "Водительское удостоверение: "
            "серия 77 77 номер 654321; "
            "Номер карты: 4111 1111 1111 1111; "
            "CVV: 987; "
            "ПИН-код: 4321; "
            "Cardholder Name: IVAN IVANOV; "
            "Адрес проживания: "
            "123456, Россия, г. Москва, "
            "ул. Тверская, д. 10, кв. 5"
        )

        prepared = processor.prepare_request(
            "crm",
            text,
        )

        expected_types = {
            PiiType.FIO,
            PiiType.BIRTH_DATE,
            PiiType.EMAIL,
            PiiType.PHONE,
            PiiType.INN,
            PiiType.PASSPORT_RF,
            PiiType.DRIVER_LICENSE,
            PiiType.BANK_CARD,
            PiiType.CVV,
            PiiType.PIN,
            PiiType.CARDHOLDER_NAME,
            PiiType.ADDRESS,
        }

        self.assertEqual(
            set(prepared.detected_types),
            expected_types,
        )
        self.assertEqual(
            prepared.entity_count,
            len(expected_types),
        )

        sensitive_values = (
            "Иванов Иван Иванович",
            "15.05.1990",
            "ivan.petrov@example.com",
            "+7 (999) 123-45-67",
            "7707083893",
            "4510 123456",
            "77 77 номер 654321",
            "4111 1111 1111 1111",
            "987",
            "4321",
            "IVAN IVANOV",
            (
                "123456, Россия, г. Москва, "
                "ул. Тверская, д. 10, кв. 5"
            ),
        )

        for value in sensitive_values:
            with self.subTest(value=value):
                self.assertNotIn(
                    value,
                    prepared.masked_text,
                )

        restored = processor.finalize_response(
            prepared,
            prepared.masked_text,
        )

        self.assertEqual(restored, text)

    def test_round_trip_preserves_wrapper_and_punctuation(self):
        processor = self.build_processor()

        text = (
            "Email:user@example.com,"
            "телефон:+7 (999) 123-45-67!"
        )

        prepared = processor.prepare_request(
            "crm",
            text,
        )

        response = (
            "BEGIN["
            + prepared.masked_text
            + "]END"
        )

        final = processor.finalize_response(
            prepared,
            response,
        )

        self.assertEqual(
            final,
            "BEGIN[" + text + "]END",
        )

    def test_repeated_values_use_distinct_tokens_and_restore(self):
        processor = self.build_processor()

        text = (
            "Email: user@example.com; "
            "повторный email: user@example.com; "
            "телефон: +7 999 123-45-67; "
            "ещё телефон: +7 999 123-45-67."
        )

        prepared = processor.prepare_request(
            "crm",
            text,
        )

        tokens = _TOKEN_PATTERN.findall(
            prepared.masked_text
        )

        self.assertEqual(len(tokens), 4)
        self.assertEqual(len(set(tokens)), 4)

        self.assertNotIn(
            "user@example.com",
            prepared.masked_text,
        )
        self.assertNotIn(
            "+7 999 123-45-67",
            prepared.masked_text,
        )

        self.assertEqual(
            processor.finalize_response(
                prepared,
                prepared.masked_text,
            ),
            text,
        )

    def test_known_tokens_can_be_demasked_after_reordering(self):
        processor = self.build_processor()

        prepared = processor.prepare_request(
            "crm",
            (
                "Email: user@example.com; "
                "телефон: +7 999 123-45-67."
            ),
        )

        tokens = _TOKEN_PATTERN.findall(
            prepared.masked_text
        )

        email_token = next(
            token
            for token in tokens
            if ":email:" in token
        )
        phone_token = next(
            token
            for token in tokens
            if ":phone:" in token
        )

        response = (
            f"Сначала телефон {phone_token}, "
            f"затем email {email_token}."
        )

        final = processor.finalize_response(
            prepared,
            response,
        )

        self.assertEqual(
            final,
            (
                "Сначала телефон "
                "+7 999 123-45-67, "
                "затем email user@example.com."
            ),
        )


if __name__ == "__main__":
    unittest.main()
