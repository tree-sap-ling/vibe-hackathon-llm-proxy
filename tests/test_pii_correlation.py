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


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class PiiCorrelationTtlTests(
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

    async def test_pending_record_expires_after_pending_ttl(
        self,
    ):
        clock = FakeClock()
        store = InMemoryCorrelationStore(
            pending_ttl_seconds=10.0,
            completed_ttl_seconds=2.0,
            cleanup_interval_seconds=1.0,
            clock=clock,
        )
        processor = self.build_processor()

        original = "Email: pending@example.com"
        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        await store.put_if_absent(
            payload_id="pending-1",
            original_payload=original,
            prepared=prepared,
        )

        clock.advance(9.0)

        self.assertIsNotNone(
            await store.get("pending-1")
        )

        clock.advance(1.0)

        self.assertIsNone(
            await store.get("pending-1")
        )

    async def test_completed_record_uses_shorter_ttl(
        self,
    ):
        clock = FakeClock()
        store = InMemoryCorrelationStore(
            pending_ttl_seconds=10.0,
            completed_ttl_seconds=2.0,
            cleanup_interval_seconds=1.0,
            clock=clock,
        )
        processor = self.build_processor()

        original = "Email: completed@example.com"
        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        record, _ = await store.put_if_absent(
            payload_id="completed-1",
            original_payload=original,
            prepared=prepared,
        )

        mode, _ = await store.resolve_existing(
            payload_id="completed-1",
            payload=record.masked_payload,
        )

        self.assertEqual(mode, "demask")

        clock.advance(1.9)

        self.assertIsNotNone(
            await store.get("completed-1")
        )

        clock.advance(0.1)

        self.assertIsNone(
            await store.get("completed-1")
        )

    async def test_demask_retry_works_before_completed_ttl(
        self,
    ):
        clock = FakeClock()
        store = InMemoryCorrelationStore(
            pending_ttl_seconds=10.0,
            completed_ttl_seconds=2.0,
            cleanup_interval_seconds=1.0,
            clock=clock,
        )
        processor = self.build_processor()

        original = "Email: retryttl@example.com"
        prepared = processor.prepare_request(
            "autocheck",
            original,
        )

        record, _ = await store.put_if_absent(
            payload_id="completed-retry",
            original_payload=original,
            prepared=prepared,
        )

        first_mode, first_record = (
            await store.resolve_existing(
                payload_id="completed-retry",
                payload=record.masked_payload,
            )
        )

        clock.advance(1.0)

        second_mode, second_record = (
            await store.resolve_existing(
                payload_id="completed-retry",
                payload=record.masked_payload,
            )
        )

        self.assertEqual(first_mode, "demask")
        self.assertEqual(second_mode, "demask")
        self.assertEqual(
            processor.finalize_response(
                first_record.prepared,
                record.masked_payload,
            ),
            original,
        )
        self.assertEqual(
            processor.finalize_response(
                second_record.prepared,
                record.masked_payload,
            ),
            original,
        )

    async def test_expired_payload_id_can_start_new_pair(
        self,
    ):
        clock = FakeClock()
        store = InMemoryCorrelationStore(
            pending_ttl_seconds=5.0,
            completed_ttl_seconds=2.0,
            cleanup_interval_seconds=1.0,
            clock=clock,
        )
        processor = self.build_processor()

        first_original = "Email: firstttl@example.com"
        first_prepared = processor.prepare_request(
            "autocheck",
            first_original,
        )

        await store.put_if_absent(
            payload_id="reusable-id",
            original_payload=first_original,
            prepared=first_prepared,
        )

        clock.advance(5.0)

        second_original = "Email: secondttl@example.com"
        second_prepared = processor.prepare_request(
            "autocheck",
            second_original,
        )

        second_record, created = (
            await store.put_if_absent(
                payload_id="reusable-id",
                original_payload=second_original,
                prepared=second_prepared,
            )
        )

        self.assertTrue(created)
        self.assertTrue(
            second_record.matches_original(
                second_original
            )
        )

    async def test_cleanup_reports_removed_count(
        self,
    ):
        clock = FakeClock()
        store = InMemoryCorrelationStore(
            pending_ttl_seconds=3.0,
            completed_ttl_seconds=2.0,
            cleanup_interval_seconds=100.0,
            clock=clock,
        )
        processor = self.build_processor()

        for index in range(2):
            original = (
                f"Email: cleanup{index}@example.com"
            )
            prepared = processor.prepare_request(
                "autocheck",
                original,
            )

            await store.put_if_absent(
                payload_id=f"cleanup-{index}",
                original_payload=original,
                prepared=prepared,
            )

        clock.advance(3.0)

        self.assertEqual(
            await store.cleanup(),
            2,
        )
        self.assertEqual(
            await store.size(),
            0,
        )

    async def test_ttl_configuration_must_be_positive(
        self,
    ):
        with self.assertRaises(ValueError):
            InMemoryCorrelationStore(
                pending_ttl_seconds=0,
            )

        with self.assertRaises(ValueError):
            InMemoryCorrelationStore(
                completed_ttl_seconds=0,
            )

        with self.assertRaises(ValueError):
            InMemoryCorrelationStore(
                cleanup_interval_seconds=0,
            )
