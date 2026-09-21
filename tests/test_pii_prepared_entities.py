import unittest

from app.pii import (
    ConsumerPolicy,
    PiiProcessor,
    PiiType,
    PolicyRegistry,
)


class PreparedEntitySpanTests(unittest.TestCase):
    def build_processor(self) -> PiiProcessor:
        policy = ConsumerPolicy(
            system_id="autocheck",
            enabled_types=frozenset(PiiType),
            demask_enabled=True,
            enabled=True,
        )

        return PiiProcessor(
            PolicyRegistry((policy,))
        )

    def test_prepared_request_keeps_exact_entity_spans(
        self,
    ):
        processor = self.build_processor()

        source = (
            "Клиент Иванов Иван Иванович, "
            "паспорт 4509 123456"
        )

        prepared = processor.prepare_request(
            "autocheck",
            source,
        )

        values = [
            (
                entity.pii_type,
                entity.start,
                entity.end,
                source[entity.start:entity.end],
            )
            for entity in prepared.entities
        ]

        self.assertEqual(
            values,
            [
                (
                    PiiType.FIO,
                    7,
                    27,
                    "Иванов Иван Иванович",
                ),
                (
                    PiiType.PASSPORT_RF,
                    37,
                    48,
                    "4509 123456",
                ),
            ],
        )

    def test_entities_are_immutable_tuple_and_count_matches(
        self,
    ):
        processor = self.build_processor()

        prepared = processor.prepare_request(
            "autocheck",
            "Email: user@example.com",
        )

        self.assertIsInstance(
            prepared.entities,
            tuple,
        )
        self.assertEqual(
            prepared.entity_count,
            len(prepared.entities),
        )

    def test_prepared_repr_does_not_embed_source_values(
        self,
    ):
        processor = self.build_processor()

        source = (
            "Email: secret.person@example.com"
        )

        prepared = processor.prepare_request(
            "autocheck",
            source,
        )

        representation = repr(prepared)

        self.assertNotIn(
            "secret.person@example.com",
            representation,
        )
        self.assertIn(
            "PiiEntity",
            representation,
        )


if __name__ == "__main__":
    unittest.main()
