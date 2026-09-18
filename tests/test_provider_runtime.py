import unittest

from app.provider_runtime import build_provider_runtimes
from app.providers import ProviderConfig


class ProviderRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_builds_runtime_for_each_provider(self):
        providers = [
            ProviderConfig(
                name="primary",
                base_url="http://primary:9000",
            ),
            ProviderConfig(
                name="fallback",
                base_url="http://fallback:9001",
            ),
        ]

        runtimes = build_provider_runtimes(
            providers,
            failure_threshold=3,
            recovery_timeout=5.0,
        )

        self.assertEqual(len(runtimes), 2)
        self.assertEqual(
            runtimes[0].config.name,
            "primary",
        )
        self.assertEqual(
            runtimes[1].config.name,
            "fallback",
        )

    async def test_provider_breakers_are_independent(self):
        providers = [
            ProviderConfig(
                name="primary",
                base_url="http://primary:9000",
            ),
            ProviderConfig(
                name="fallback",
                base_url="http://fallback:9001",
            ),
        ]

        runtimes = build_provider_runtimes(
            providers,
            failure_threshold=1,
            recovery_timeout=5.0,
        )

        primary = runtimes[0]
        fallback = runtimes[1]

        await primary.circuit_breaker.record_failure()

        primary_snapshot = (
            await primary.circuit_breaker.snapshot()
        )
        fallback_snapshot = (
            await fallback.circuit_breaker.snapshot()
        )

        self.assertEqual(
            primary_snapshot["state"],
            "open",
        )
        self.assertEqual(
            fallback_snapshot["state"],
            "closed",
        )
        self.assertEqual(
            fallback_snapshot["failure_count"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
