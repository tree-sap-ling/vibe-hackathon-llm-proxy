import unittest

from app.pii import (
    ConsumerPolicy,
    PiiMetrics,
    PiiProcessor,
    PiiType,
    PolicyRegistry,
)


class PiiMetricsTests(
    unittest.IsolatedAsyncioTestCase
):
    def build_processor(self) -> PiiProcessor:
        policy = ConsumerPolicy(
            system_id="crm",
            enabled_types=frozenset(
                {
                    PiiType.EMAIL,
                    PiiType.PHONE,
                }
            ),
            demask_enabled=True,
            enabled=True,
        )

        return PiiProcessor(
            PolicyRegistry((policy,))
        )

    async def test_initial_snapshot_is_zero(self):
        metrics = PiiMetrics()

        snapshot = await metrics.snapshot()

        self.assertEqual(
            snapshot["processed_requests"],
            0,
        )
        self.assertEqual(
            snapshot["requests_with_pii"],
            0,
        )
        self.assertEqual(
            snapshot["detected_entities"],
            0,
        )
        self.assertEqual(
            snapshot["processing_ms"]["samples"],
            0,
        )
        self.assertEqual(
            snapshot["processing_ms"]["avg"],
            0.0,
        )
        self.assertEqual(
            snapshot["processing_ms"]["p95"],
            0.0,
        )
        self.assertEqual(
            snapshot["requests_by_type"],
            {},
        )

    async def test_record_tracks_safe_aggregate_metrics(
        self,
    ):
        processor = self.build_processor()
        metrics = PiiMetrics()

        first = processor.prepare_request(
            "crm",
            (
                "Email alpha@example.com, "
                "телефон +7 999 111-22-33."
            ),
        )
        second = processor.prepare_request(
            "crm",
            "Email beta@example.com.",
        )

        await metrics.record(first)
        await metrics.record(second)

        snapshot = await metrics.snapshot()

        self.assertEqual(
            snapshot["processed_requests"],
            2,
        )
        self.assertEqual(
            snapshot["requests_with_pii"],
            2,
        )
        self.assertEqual(
            snapshot["detected_entities"],
            3,
        )
        self.assertEqual(
            snapshot["processing_ms"]["samples"],
            2,
        )
        self.assertGreaterEqual(
            snapshot["processing_ms"]["avg"],
            0.0,
        )
        self.assertGreaterEqual(
            snapshot["processing_ms"]["p95"],
            snapshot["processing_ms"]["p50"],
        )
        self.assertGreaterEqual(
            snapshot["processing_ms"]["max"],
            snapshot["processing_ms"]["p95"],
        )
        self.assertGreater(
            snapshot["average_rps_since_start"],
            0.0,
        )
        self.assertEqual(
            snapshot["requests_by_type"],
            {
                "email": 2,
                "phone": 1,
            },
        )

    async def test_snapshot_never_contains_pii_values(
        self,
    ):
        processor = self.build_processor()
        metrics = PiiMetrics()

        prepared = processor.prepare_request(
            "crm",
            (
                "Email secret.person@example.com, "
                "телефон +7 999 123-45-67."
            ),
        )

        await metrics.record(prepared)

        snapshot = await metrics.snapshot()
        serialized = repr(snapshot)

        self.assertNotIn(
            "secret.person@example.com",
            serialized,
        )
        self.assertNotIn(
            "+7 999 123-45-67",
            serialized,
        )
        self.assertNotIn(
            prepared.masked_text,
            serialized,
        )
        self.assertNotIn(
            "MaskingVault",
            serialized,
        )

        self.assertIn(
            "'email': 1",
            serialized,
        )
        self.assertIn(
            "'phone': 1",
            serialized,
        )

    async def test_latency_sample_limit_is_bounded(
        self,
    ):
        processor = self.build_processor()
        metrics = PiiMetrics(
            latency_sample_limit=2
        )

        for index in range(3):
            prepared = processor.prepare_request(
                "crm",
                f"Email user{index}@example.com",
            )
            await metrics.record(prepared)

        snapshot = await metrics.snapshot()

        self.assertEqual(
            snapshot["processed_requests"],
            3,
        )
        self.assertEqual(
            snapshot["processing_ms"]["samples"],
            2,
        )

    def test_latency_sample_limit_must_be_positive(
        self,
    ):
        with self.assertRaises(ValueError):
            PiiMetrics(
                latency_sample_limit=0
            )


if __name__ == "__main__":
    unittest.main()
