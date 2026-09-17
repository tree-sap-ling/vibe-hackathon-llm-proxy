import unittest

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


class FakeResponse:
    def __init__(self):
        self.closed = False

    async def aiter_raw(self):
        yield b"data: first\n\n"
        yield b"data: second\n\n"
        yield b"data: [DONE]\n\n"

    async def aclose(self):
        self.closed = True


class StreamingRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_relay_stream_forwards_and_cleans_up(self):
        response = FakeResponse()
        stats = FakeStats()
        gate = FakeGate()

        chunks = []

        async for chunk in relay_stream(
            response,
            stats,
            gate,
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


if __name__ == "__main__":
    unittest.main()
