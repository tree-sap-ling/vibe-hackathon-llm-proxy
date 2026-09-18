import unittest
from unittest.mock import patch

from app.circuit_breaker import CircuitBreaker


class CircuitBreakerTests(unittest.IsolatedAsyncioTestCase):
    async def test_opens_after_failure_threshold_and_recovers(self):
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=5.0,
        )

        self.assertTrue(await breaker.allow_request())

        await breaker.record_failure()

        snapshot = await breaker.snapshot()

        self.assertEqual(snapshot["state"], "closed")
        self.assertEqual(snapshot["failure_count"], 1)

        with patch(
            "app.circuit_breaker.time.monotonic",
            return_value=100.0,
        ):
            await breaker.record_failure()

        snapshot = await breaker.snapshot()

        self.assertEqual(snapshot["state"], "open")
        self.assertEqual(snapshot["failure_count"], 2)

        with patch(
            "app.circuit_breaker.time.monotonic",
            return_value=103.0,
        ):
            self.assertFalse(await breaker.allow_request())

        with patch(
            "app.circuit_breaker.time.monotonic",
            return_value=106.0,
        ):
            self.assertTrue(await breaker.allow_request())

        snapshot = await breaker.snapshot()

        self.assertEqual(snapshot["state"], "half_open")

        self.assertFalse(await breaker.allow_request())

        await breaker.record_success()

        snapshot = await breaker.snapshot()

        self.assertEqual(snapshot["state"], "closed")
        self.assertEqual(snapshot["failure_count"], 0)

    async def test_failed_half_open_probe_reopens_circuit(self):
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=5.0,
        )

        with patch(
            "app.circuit_breaker.time.monotonic",
            return_value=100.0,
        ):
            await breaker.record_failure()

        with patch(
            "app.circuit_breaker.time.monotonic",
            return_value=106.0,
        ):
            self.assertTrue(await breaker.allow_request())

        with patch(
            "app.circuit_breaker.time.monotonic",
            return_value=107.0,
        ):
            await breaker.record_failure()

        snapshot = await breaker.snapshot()

        self.assertEqual(snapshot["state"], "open")

        with patch(
            "app.circuit_breaker.time.monotonic",
            return_value=110.0,
        ):
            self.assertFalse(await breaker.allow_request())


if __name__ == "__main__":
    unittest.main()
