import unittest

from app.stats import ProxyStats


class ProxyStatsTests(unittest.IsolatedAsyncioTestCase):
    async def test_increment_and_snapshot(self):
        stats = ProxyStats()

        await stats.increment("total_requests")
        await stats.increment("total_requests")
        await stats.increment("overload_rejections")

        snapshot = await stats.snapshot()

        self.assertEqual(snapshot["total_requests"], 2)
        self.assertEqual(snapshot["completed_requests"], 0)
        self.assertEqual(snapshot["overload_rejections"], 1)
        self.assertEqual(snapshot["upstream_errors"], 0)
        self.assertEqual(snapshot["upstream_timeouts"], 0)


if __name__ == "__main__":
    unittest.main()
