import unittest

from app.pii import (
    PiiEntity,
    PiiType,
    build_default_registry,
)
from app.pii.public_masking import (
    mask_public_value,
    render_public_mask,
)


class PublicMaskingTests(unittest.TestCase):
    def test_published_example_matches_exactly(self):
        source = (
            "Клиент Иванов Иван Иванович, "
            "паспорт 4509 123456"
        )
        expected = (
            "Клиент И. И. И., "
            "паспорт 45** ****56"
        )

        entities = build_default_registry().detect(
            source
        )

        self.assertEqual(
            render_public_mask(
                source,
                entities,
            ),
            expected,
        )

    def test_fio_uses_initials(self):
        self.assertEqual(
            mask_public_value(
                PiiType.FIO,
                "Иванов Иван Иванович",
            ),
            "И. И. И.",
        )

    def test_passport_preserves_outer_digits(self):
        self.assertEqual(
            mask_public_value(
                PiiType.PASSPORT_RF,
                "4509 123456",
            ),
            "45** ****56",
        )

    def test_passport_words_are_preserved(self):
        self.assertEqual(
            mask_public_value(
                PiiType.PASSPORT_RF,
                "45 10 номер 123456",
            ),
            "45 ** номер ****56",
        )

    def test_generic_mask_preserves_separators(self):
        self.assertEqual(
            mask_public_value(
                PiiType.EMAIL,
                "user@example.com",
            ),
            "****@*******.***",
        )
        self.assertEqual(
            mask_public_value(
                PiiType.PHONE,
                "+7 (999) 123-45-67",
            ),
            "+* (***) ***-**-**",
        )

    def test_sentence_punctuation_stays_outside_span(self):
        source = (
            "Место рождения клиента: "
            "г. Казань."
        )

        entities = build_default_registry().detect(
            source,
            enabled_types={
                PiiType.BIRTH_PLACE,
            },
        )

        result = render_public_mask(
            source,
            entities,
        )

        self.assertEqual(
            result,
            "Место рождения клиента: "
            "*. ******.",
        )
        self.assertTrue(
            result.endswith(".")
        )

    def test_generic_replacement_keeps_length(self):
        value = "15 мая 1990 года"

        masked = mask_public_value(
            PiiType.BIRTH_DATE,
            value,
        )

        self.assertEqual(
            len(masked),
            len(value),
        )

        for source_char, masked_char in zip(
            value,
            masked,
        ):
            if source_char.isalnum():
                self.assertEqual(
                    masked_char,
                    "*",
                )
            else:
                self.assertEqual(
                    masked_char,
                    source_char,
                )

    def test_render_rejects_overlapping_entities(self):
        with self.assertRaises(ValueError):
            render_public_mask(
                "abcdefghij",
                [
                    PiiEntity(
                        pii_type=PiiType.EMAIL,
                        start=0,
                        end=6,
                    ),
                    PiiEntity(
                        pii_type=PiiType.PHONE,
                        start=4,
                        end=10,
                    ),
                ],
            )

    def test_render_rejects_span_outside_source(self):
        with self.assertRaises(ValueError):
            render_public_mask(
                "abc",
                [
                    PiiEntity(
                        pii_type=PiiType.EMAIL,
                        start=0,
                        end=4,
                    ),
                ],
            )


if __name__ == "__main__":
    unittest.main()
