import unittest

from app.pii import (
    ConsumerPolicy,
    CorrelationConflictError,
    InMemoryCorrelationStore,
    PiiProcessor,
    PiiType,
    PolicyRegistry,
    build_default_registry,
)
from app.pii.public_masking import render_public_mask


class PublicMaskCorrelationTests(
    unittest.IsolatedAsyncioTestCase
):
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

    async def test_store_can_correlate_public_mask(self):
        processor = self.build_processor()
        store = InMemoryCorrelationStore()

        original = (
            "Клиент Иванов Иван Иванович, "
            "паспорт 4509 123456"
        )

        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        entities = build_default_registry().detect(
            original
        )

        public_mask = render_public_mask(
            original,
            entities,
        )

        self.assertEqual(
            public_mask,
            (
                "Клиент ****** **** ********, "
                "паспорт **** ******"
            ),
        )

        self.assertNotEqual(
            public_mask,
            prepared.masked_text,
        )

        record, created = await store.put_if_absent(
            payload_id="public-pair-1",
            original_payload=original,
            prepared=prepared,
            masked_payload=public_mask,
        )

        self.assertTrue(created)
        self.assertEqual(
            record.masked_payload,
            public_mask,
        )

        mode, retry_record = (
            await store.resolve_existing(
                payload_id="public-pair-1",
                payload=original,
            )
        )

        self.assertEqual(
            mode,
            "mask_retry",
        )
        self.assertEqual(
            retry_record.masked_payload,
            public_mask,
        )

        mode, demask_record = (
            await store.resolve_existing(
                payload_id="public-pair-1",
                payload=public_mask,
            )
        )

        self.assertEqual(
            mode,
            "demask",
        )

        restored = processor.finalize_response(
            demask_record.prepared,
            demask_record.prepared.masked_text,
        )

        self.assertEqual(
            restored,
            original,
        )

    async def test_internal_token_mask_is_not_public_mask(
        self,
    ):
        processor = self.build_processor()
        store = InMemoryCorrelationStore()

        original = "Email: user@example.com"

        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        entities = build_default_registry().detect(
            original
        )
        public_mask = render_public_mask(
            original,
            entities,
        )

        await store.put_if_absent(
            payload_id="public-pair-2",
            original_payload=original,
            prepared=prepared,
            masked_payload=public_mask,
        )

        with self.assertRaises(
            CorrelationConflictError
        ):
            await store.resolve_existing(
                payload_id="public-pair-2",
                payload=prepared.masked_text,
            )

    async def test_default_behavior_remains_compatible(
        self,
    ):
        processor = self.build_processor()
        store = InMemoryCorrelationStore()

        original = "Телефон: +7 999 123-45-67"

        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        record, created = await store.put_if_absent(
            payload_id="legacy-pair",
            original_payload=original,
            prepared=prepared,
        )

        self.assertTrue(created)
        self.assertEqual(
            record.masked_payload,
            prepared.masked_text,
        )


if __name__ == "__main__":
    unittest.main()
