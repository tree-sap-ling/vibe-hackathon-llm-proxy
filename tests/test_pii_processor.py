import unittest

from app.pii import (
    ConsumerDisabledError,
    ConsumerPolicy,
    PiiProcessor,
    PiiType,
    PolicyRegistry,
    UnknownConsumerError,
)


class PiiProcessorTests(unittest.TestCase):
    def build_processor(
        self,
        *,
        enabled_types=frozenset(
            {
                PiiType.EMAIL,
                PiiType.PHONE,
            }
        ),
        demask_enabled=True,
        enabled=True,
    ):
        policy = ConsumerPolicy(
            system_id="crm",
            enabled_types=enabled_types,
            demask_enabled=demask_enabled,
            enabled=enabled,
        )

        return PiiProcessor(
            PolicyRegistry((policy,))
        )

    def test_prepare_masks_enabled_pii(self):
        processor = self.build_processor()
        text = (
            "Email user@example.com, "
            "телефон +7 999 123-45-67."
        )

        prepared = processor.prepare_request(
            "crm",
            text,
        )

        self.assertNotIn(
            "user@example.com",
            prepared.masked_text,
        )
        self.assertNotIn(
            "+7 999 123-45-67",
            prepared.masked_text,
        )
        self.assertEqual(
            prepared.entity_count,
            2,
        )
        self.assertEqual(
            prepared.detected_types,
            (
                PiiType.EMAIL,
                PiiType.PHONE,
            ),
        )

    def test_policy_filters_disabled_pii_type(self):
        processor = self.build_processor(
            enabled_types=frozenset(
                {PiiType.EMAIL}
            )
        )
        text = (
            "Email user@example.com, "
            "телефон +7 999 123-45-67."
        )

        prepared = processor.prepare_request(
            "crm",
            text,
        )

        self.assertNotIn(
            "user@example.com",
            prepared.masked_text,
        )
        self.assertIn(
            "+7 999 123-45-67",
            prepared.masked_text,
        )
        self.assertEqual(
            prepared.detected_types,
            (PiiType.EMAIL,),
        )

    def test_finalize_demasks_response_when_enabled(self):
        processor = self.build_processor()
        text = "Ответьте user@example.com."

        prepared = processor.prepare_request(
            "crm",
            text,
        )

        response = (
            "LLM повторил: "
            + prepared.masked_text
        )

        final = processor.finalize_response(
            prepared,
            response,
        )

        self.assertIn(
            "user@example.com",
            final,
        )
        self.assertNotIn(
            "<PII:",
            final,
        )

    def test_finalize_keeps_mask_when_demask_disabled(self):
        processor = self.build_processor(
            demask_enabled=False
        )
        text = "Email user@example.com."

        prepared = processor.prepare_request(
            "crm",
            text,
        )

        final = processor.finalize_response(
            prepared,
            prepared.masked_text,
        )

        self.assertNotIn(
            "user@example.com",
            final,
        )
        self.assertIn(
            "<PII:email:",
            final,
        )

    def test_unknown_consumer_is_rejected(self):
        processor = self.build_processor()

        with self.assertRaises(
            UnknownConsumerError
        ):
            processor.prepare_request(
                "unknown",
                "user@example.com",
            )

    def test_disabled_consumer_is_rejected(self):
        processor = self.build_processor(
            enabled=False
        )

        with self.assertRaises(
            ConsumerDisabledError
        ):
            processor.prepare_request(
                "crm",
                "user@example.com",
            )

    def test_prepared_repr_does_not_expose_original_pii(self):
        processor = self.build_processor()

        prepared = processor.prepare_request(
            "crm",
            "Email secret.person@example.com",
        )

        representation = repr(prepared)

        self.assertNotIn(
            "secret.person@example.com",
            representation,
        )
        self.assertIn(
            "values=<redacted>",
            representation,
        )

    def test_response_without_known_tokens_is_unchanged(self):
        processor = self.build_processor()

        prepared = processor.prepare_request(
            "crm",
            "Email user@example.com",
        )

        response = "Обычный ответ без токенов."

        self.assertEqual(
            processor.finalize_response(
                prepared,
                response,
            ),
            response,
        )


if __name__ == "__main__":
    unittest.main()
