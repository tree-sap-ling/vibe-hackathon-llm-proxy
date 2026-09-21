import unittest

from app.pii import (
    PiiEntity,
    PiiType,
    build_default_registry,
    mask_text,
)


class PiiMaskingTests(unittest.TestCase):
    def test_round_trip_preserves_original_text_exactly(self):
        text = (
            "Пишите на user@example.com, "
            "или звоните +7 (999) 123-45-67!"
        )
        entities = build_default_registry().detect(text)

        result = mask_text(
            text,
            entities,
            token_namespace="abcdef12",
        )

        restored = result.vault.demask(result.text)

        self.assertEqual(restored, text)

    def test_masked_text_does_not_contain_original_values(self):
        text = (
            "Email user@example.com, "
            "телефон 8 999 123 45 67."
        )
        entities = build_default_registry().detect(text)

        result = mask_text(
            text,
            entities,
            token_namespace="abcdef12",
        )

        self.assertNotIn(
            "user@example.com",
            result.text,
        )
        self.assertNotIn(
            "8 999 123 45 67",
            result.text,
        )

        self.assertIn(
            "<PII:email:1:abcdef12>",
            result.text,
        )
        self.assertIn(
            "<PII:phone:1:abcdef12>",
            result.text,
        )

    def test_repeated_values_are_restored_by_position(self):
        text = (
            "user@example.com и снова "
            "user@example.com."
        )
        entities = build_default_registry().detect(text)

        result = mask_text(
            text,
            entities,
            token_namespace="abcdef12",
        )

        self.assertIn(
            "<PII:email:1:abcdef12>",
            result.text,
        )
        self.assertIn(
            "<PII:email:2:abcdef12>",
            result.text,
        )
        self.assertEqual(
            result.vault.demask(result.text),
            text,
        )

    def test_unknown_token_is_not_demasked(self):
        text = "Email user@example.com"
        entities = build_default_registry().detect(text)

        result = mask_text(
            text,
            entities,
            token_namespace="abcdef12",
        )

        response = (
            result.text
            + " <PII:phone:99:deadbeef>"
        )

        restored = result.vault.demask(response)

        self.assertIn(
            "user@example.com",
            restored,
        )
        self.assertIn(
            "<PII:phone:99:deadbeef>",
            restored,
        )

    def test_vault_repr_does_not_expose_original_values(self):
        text = "Email secret.person@example.com"
        entities = build_default_registry().detect(text)

        result = mask_text(
            text,
            entities,
            token_namespace="abcdef12",
        )

        representation = repr(result.vault)

        self.assertNotIn(
            "secret.person@example.com",
            representation,
        )
        self.assertIn(
            "values=<redacted>",
            representation,
        )

    def test_result_reports_types_without_values(self):
        text = (
            "Email user@example.com, "
            "телефон +7 999 123-45-67."
        )
        entities = build_default_registry().detect(text)

        result = mask_text(
            text,
            entities,
            token_namespace="abcdef12",
        )

        self.assertEqual(result.entity_count, 2)
        self.assertEqual(
            result.detected_types,
            (
                PiiType.EMAIL,
                PiiType.PHONE,
            ),
        )

    def test_rejects_overlapping_entities(self):
        text = "abcdefghij"

        entities = [
            PiiEntity(
                pii_type=PiiType.EMAIL,
                start=0,
                end=8,
            ),
            PiiEntity(
                pii_type=PiiType.PHONE,
                start=4,
                end=10,
            ),
        ]

        with self.assertRaises(ValueError):
            mask_text(
                text,
                entities,
                token_namespace="abcdef12",
            )

    def test_rejects_span_outside_source_text(self):
        with self.assertRaises(ValueError):
            mask_text(
                "short",
                [
                    PiiEntity(
                        pii_type=PiiType.EMAIL,
                        start=0,
                        end=10,
                    )
                ],
                token_namespace="abcdef12",
            )

    def test_namespace_collision_is_rejected(self):
        text = "Текст содержит abcdef12 внутри."

        with self.assertRaises(ValueError):
            mask_text(
                text,
                [],
                token_namespace="abcdef12",
            )


if __name__ == "__main__":
    unittest.main()
