import unittest

import httpx

from app.streaming import relay_stream


class FakeStats:
    def __init__(self):
        self.values = {}

    async def increment(self, field):
        self.values[field] = self.values.get(field, 0) + 1


class FakeGate:
    def __init__(self):
        self.release_calls = 0

    async def release(self):
        self.release_calls += 1


class FakeBreaker:
    def __init__(self):
        self.success_calls = 0
        self.failure_calls = 0

    async def record_success(self):
        self.success_calls += 1

    async def record_failure(self):
        self.failure_calls += 1


class FakeResponse:
    status_code = 200

    def __init__(self):
        self.closed = False

    async def aiter_raw(self):
        yield b"data: first\n\n"
        yield b"data: second\n\n"
        yield b"data: [DONE]\n\n"

    async def aclose(self):
        self.closed = True


class FailingResponse:
    status_code = 200

    def __init__(self):
        self.closed = False

    async def aiter_raw(self):
        yield b"data: first\n\n"

        raise httpx.ReadError(
            "stream failed",
            request=httpx.Request(
                "POST",
                "http://mock-provider",
            ),
        )

    async def aclose(self):
        self.closed = True


class StreamingRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_relay_stream_forwards_and_cleans_up(self):
        response = FakeResponse()
        stats = FakeStats()
        gate = FakeGate()
        breaker = FakeBreaker()

        chunks = []

        async for chunk in relay_stream(
            response,
            stats,
            gate,
            breaker,
        ):
            chunks.append(chunk)

        self.assertEqual(
            b"".join(chunks),
            (
                b"data: first\n\n"
                b"data: second\n\n"
                b"data: [DONE]\n\n"
            ),
        )
        self.assertTrue(response.closed)
        self.assertEqual(gate.release_calls, 1)
        self.assertEqual(
            stats.values.get("completed_requests"),
            1,
        )
        self.assertEqual(breaker.success_calls, 1)
        self.assertEqual(breaker.failure_calls, 0)

    async def test_relay_stream_records_failure(self):
        response = FailingResponse()
        stats = FakeStats()
        gate = FakeGate()
        breaker = FakeBreaker()

        chunks = []

        async for chunk in relay_stream(
            response,
            stats,
            gate,
            breaker,
        ):
            chunks.append(chunk)

        self.assertEqual(
            chunks,
            [b"data: first\n\n"],
        )
        self.assertTrue(response.closed)
        self.assertEqual(gate.release_calls, 1)
        self.assertEqual(
            stats.values.get("upstream_errors"),
            1,
        )
        self.assertIsNone(
            stats.values.get("completed_requests")
        )
        self.assertEqual(breaker.success_calls, 0)
        self.assertEqual(breaker.failure_calls, 1)


if __name__ == "__main__":
    unittest.main()
