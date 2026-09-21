import unittest

from app.pii import (
    ConsumerPolicy,
    CorrelationConflictError,
    InMemoryCorrelationStore,
    PiiProcessor,
    PiiType,
    PolicyRegistry,
)


class PiiCorrelationStoreTests(
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

    async def test_new_payload_id_is_inserted_once(
        self,
    ):
        processor = self.build_processor()
        store = InMemoryCorrelationStore()

        original = (
            "Email: first.person@example.com"
        )
        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        record, created = await store.put_if_absent(
            payload_id="pair-1",
            original_payload=original,
            prepared=prepared,
        )

        self.assertTrue(created)
        self.assertEqual(
            record.masked_payload,
            prepared.masked_text,
        )
        self.assertEqual(
            await store.size(),
            1,
        )

    async def test_original_retry_returns_same_mask(
        self,
    ):
        processor = self.build_processor()
        store = InMemoryCorrelationStore()

        original = (
            "Email: retry.person@example.com"
        )
        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        first, created = await store.put_if_absent(
            payload_id="pair-retry",
            original_payload=original,
            prepared=prepared,
        )

        self.assertTrue(created)

        mode, existing = (
            await store.resolve_existing(
                payload_id="pair-retry",
                payload=original,
            )
        )

        self.assertEqual(mode, "mask_retry")
        self.assertEqual(
            existing.masked_payload,
            first.masked_payload,
        )

    async def test_masked_payload_resolves_to_demask(
        self,
    ):
        processor = self.build_processor()
        store = InMemoryCorrelationStore()

        original = (
            "Телефон: +7 999 123-45-67."
        )
        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        record, _ = await store.put_if_absent(
            payload_id="pair-demask",
            original_payload=original,
            prepared=prepared,
        )

        mode, existing = (
            await store.resolve_existing(
                payload_id="pair-demask",
                payload=record.masked_payload,
            )
        )

        self.assertEqual(mode, "demask")

        restored = processor.finalize_response(
            existing.prepared,
            record.masked_payload,
        )

        self.assertEqual(restored, original)

    async def test_demask_retry_is_idempotent(
        self,
    ):
        processor = self.build_processor()
        store = InMemoryCorrelationStore()

        original = (
            "Email: stable@example.com"
        )
        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        record, _ = await store.put_if_absent(
            payload_id="pair-demask-retry",
            original_payload=original,
            prepared=prepared,
        )

        for _ in range(2):
            mode, existing = (
                await store.resolve_existing(
                    payload_id=(
                        "pair-demask-retry"
                    ),
                    payload=record.masked_payload,
                )
            )

            self.assertEqual(mode, "demask")
            self.assertEqual(
                processor.finalize_response(
                    existing.prepared,
                    record.masked_payload,
                ),
                original,
            )

    async def test_same_id_with_other_payload_conflicts(
        self,
    ):
        processor = self.build_processor()
        store = InMemoryCorrelationStore()

        original = (
            "Email: owner@example.com"
        )
        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        await store.put_if_absent(
            payload_id="pair-conflict",
            original_payload=original,
            prepared=prepared,
        )

        with self.assertRaises(
            CorrelationConflictError
        ):
            await store.resolve_existing(
                payload_id="pair-conflict",
                payload=(
                    "Email: attacker@example.com"
                ),
            )

    async def test_concurrent_insert_keeps_one_record(
        self,
    ):
        processor = self.build_processor()
        store = InMemoryCorrelationStore()

        first_original = (
            "Email: first@example.com"
        )
        second_original = (
            "Email: second@example.com"
        )

        first_prepared = processor.prepare_request(
            "autocheck",
            first_original,
        )
        second_prepared = processor.prepare_request(
            "autocheck",
            second_original,
        )

        import asyncio

        results = await asyncio.gather(
            store.put_if_absent(
                payload_id="pair-race",
                original_payload=first_original,
                prepared=first_prepared,
            ),
            store.put_if_absent(
                payload_id="pair-race",
                original_payload=second_original,
                prepared=second_prepared,
            ),
        )

        created_count = sum(
            1
            for _, created in results
            if created
        )

        self.assertEqual(created_count, 1)
        self.assertEqual(
            await store.size(),
            1,
        )

    async def test_empty_payload_id_is_rejected(
        self,
    ):
        store = InMemoryCorrelationStore()

        with self.assertRaises(ValueError):
            await store.get("   ")


if __name__ == "__main__":
    unittest.main()
