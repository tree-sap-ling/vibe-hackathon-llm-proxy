import unittest

from app.stats import ProxyStats


class ProxyStatsTests(unittest.IsolatedAsyncioTestCase):
    async def test_increment_and_snapshot(self):
        stats = ProxyStats()

        await stats.increment("total_requests")
        await stats.increment("total_requests")
        await stats.increment("overload_rejections")
        await stats.increment("circuit_open_rejections")

        snapshot = await stats.snapshot()

        self.assertEqual(snapshot["total_requests"], 2)
        self.assertEqual(snapshot["completed_requests"], 0)
        self.assertEqual(snapshot["overload_rejections"], 1)
        self.assertEqual(snapshot["circuit_open_rejections"], 1)
        self.assertEqual(snapshot["upstream_errors"], 0)
        self.assertEqual(snapshot["upstream_timeouts"], 0)
        self.assertEqual(snapshot["tps"], 0.0)
        self.assertEqual(snapshot["token_usage"]["samples"], 0)
        self.assertEqual(
            snapshot["token_usage"]["provider_reported_total_tokens"],
            0,
        )
        self.assertEqual(
            snapshot["token_usage"]["observed_seconds"],
            0.0,
        )

    async def test_provider_reported_token_tps(self):
        stats = ProxyStats()

        self.assertTrue(
            await stats.record_token_usage(
                total_tokens=20,
                observed_seconds=0.5,
            )
        )
        self.assertTrue(
            await stats.record_token_usage(
                total_tokens=10,
                observed_seconds=0.25,
            )
        )

        snapshot = await stats.snapshot()

        self.assertEqual(snapshot["token_usage"]["samples"], 2)
        self.assertEqual(
            snapshot["token_usage"]["provider_reported_total_tokens"],
            30,
        )
        self.assertEqual(
            snapshot["token_usage"]["observed_seconds"],
            0.75,
        )
        self.assertEqual(snapshot["tps"], 40.0)

    async def test_invalid_token_usage_is_ignored(self):
        stats = ProxyStats()

        self.assertFalse(
            await stats.record_token_usage(
                total_tokens=-1,
                observed_seconds=1.0,
            )
        )
        self.assertFalse(
            await stats.record_token_usage(
                total_tokens=True,
                observed_seconds=1.0,
            )
        )
        self.assertFalse(
            await stats.record_token_usage(
                total_tokens=10,
                observed_seconds=0.0,
            )
        )

        snapshot = await stats.snapshot()

        self.assertEqual(snapshot["tps"], 0.0)
        self.assertEqual(snapshot["token_usage"]["samples"], 0)


if __name__ == "__main__":
    unittest.main()
