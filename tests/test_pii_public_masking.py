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
    def test_published_example_is_fully_hidden(self):
        source = (
            "Клиент Иванов Иван Иванович, "
            "паспорт 4509 123456"
        )
        expected = (
            "Клиент ****** **** ********, "
            "паспорт **** ******"
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

    def test_fio_is_fully_hidden(self):
        self.assertEqual(
            mask_public_value(
                PiiType.FIO,
                "Иванов Иван Иванович",
            ),
            "****** **** ********",
        )

    def test_passport_is_fully_hidden(self):
        self.assertEqual(
            mask_public_value(
                PiiType.PASSPORT_RF,
                "4509 123456",
            ),
            "**** ******",
        )

    def test_passport_words_are_preserved(self):
        self.assertEqual(
            mask_public_value(
                PiiType.PASSPORT_RF,
                "45 10 номер 123456",
            ),
            "** ** номер ******",
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
            "г. ******.",
        )
        self.assertTrue(
            result.endswith(".")
        )

    def test_generic_replacement_keeps_length(self):
        value = "user@example.com"

        masked = mask_public_value(
            PiiType.EMAIL,
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

    def test_date_keeps_year_service_word(self):
        self.assertEqual(
            mask_public_value(
                PiiType.BIRTH_DATE,
                "15 мая 1990 года",
            ),
            "** *** **** года",
        )

    def test_passport_issue_date_keeps_year_service_word(self):
        self.assertEqual(
            mask_public_value(
                PiiType.PASSPORT_ISSUE_DATE,
                "21 августа 2015 года",
            ),
            "** ******* **** года",
        )

    def test_driver_license_keeps_number_service_word(self):
        self.assertEqual(
            mask_public_value(
                PiiType.DRIVER_LICENSE,
                "66 66 номер 654321",
            ),
            "** ** номер ******",
        )

    def test_full_address_keeps_component_service_labels(self):
        value = (
            "123456, Россия, г. Москва, "
            "ул. Тверская, д. 10, кв. 5"
        )

        self.assertEqual(
            mask_public_value(
                PiiType.ADDRESS,
                value,
            ),
            (
                "******, ******, г. ******, "
                "ул. ********, д. **, кв. *"
            ),
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
