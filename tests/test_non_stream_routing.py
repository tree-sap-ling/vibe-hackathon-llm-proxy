import asyncio
import unittest

import httpx

from app.non_stream_routing import route_non_stream_request
from app.provider_runtime import build_provider_runtimes
from app.providers import ProviderConfig


class FakeStats:
    def __init__(self):
        self.values = {}

    async def increment(self, field):
        self.values[field] = self.values.get(field, 0) + 1


class FakeHttpClient:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append(url)

        action = self.behavior[url]

        if action == "unavailable":
            raise httpx.ConnectError(
                "unavailable",
                request=httpx.Request("POST", url),
            )

        if action == "timeout":
            raise httpx.ReadTimeout(
                "timeout",
                request=httpx.Request("POST", url),
            )

        if isinstance(action, int):
            return httpx.Response(
                action,
                json={"provider": url},
                request=httpx.Request("POST", url),
            )

        raise AssertionError(f"Unknown action: {action}")


class SlowPrimaryHttpClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append(url)

        if url.startswith("http://primary:9000"):
            await asyncio.sleep(0.05)

            return httpx.Response(
                200,
                json={"provider": "primary"},
                request=httpx.Request("POST", url),
            )

        if url.startswith("http://fallback:9001"):
            return httpx.Response(
                200,
                json={"provider": "fallback"},
                request=httpx.Request("POST", url),
            )

        raise AssertionError(f"Unexpected URL: {url}")


def make_runtimes():
    return build_provider_runtimes(
        providers=[
            ProviderConfig(
                name="primary",
                base_url="http://primary:9000",
            ),
            ProviderConfig(
                name="fallback",
                base_url="http://fallback:9001",
            ),
        ],
        failure_threshold=3,
        recovery_timeout=5.0,
    )


class NonStreamRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_total_routing_budget_stops_before_fallback(self):
        runtimes = make_runtimes()
        client = SlowPrimaryHttpClient()
        stats = FakeStats()

        result = await route_non_stream_request(
            client,
            runtimes,
            {"messages": []},
            stats,
            routing_timeout=0.01,
        )

        self.assertIsNone(result.response)
        self.assertEqual(result.error, "timeout")

        self.assertEqual(
            client.calls,
            [
                "http://primary:9000/v1/chat/completions",
            ],
        )

        self.assertEqual(
            stats.values.get("upstream_timeouts"),
            1,
        )


    async def test_primary_success_does_not_call_fallback(self):
        runtimes = make_runtimes()

        client = FakeHttpClient(
            {
                "http://primary:9000/v1/chat/completions": 200,
                "http://fallback:9001/v1/chat/completions": 200,
            }
        )

        result = await route_non_stream_request(
            client,
            runtimes,
            {"messages": []},
            FakeStats(),
        )

        self.assertEqual(result.response.status_code, 200)
        self.assertEqual(result.provider_name, "primary")
        self.assertEqual(len(client.calls), 1)

    async def test_network_failure_uses_fallback(self):
        runtimes = make_runtimes()

        client = FakeHttpClient(
            {
                "http://primary:9000/v1/chat/completions": (
                    "unavailable"
                ),
                "http://fallback:9001/v1/chat/completions": 200,
            }
        )

        result = await route_non_stream_request(
            client,
            runtimes,
            {"messages": []},
            FakeStats(),
        )

        self.assertEqual(result.response.status_code, 200)
        self.assertEqual(result.provider_name, "fallback")
        self.assertEqual(len(client.calls), 2)

    async def test_primary_5xx_uses_fallback(self):
        runtimes = make_runtimes()

        client = FakeHttpClient(
            {
                "http://primary:9000/v1/chat/completions": 503,
                "http://fallback:9001/v1/chat/completions": 200,
            }
        )

        result = await route_non_stream_request(
            client,
            runtimes,
            {"messages": []},
            FakeStats(),
        )

        self.assertEqual(result.response.status_code, 200)
        self.assertEqual(result.provider_name, "fallback")

    async def test_primary_4xx_does_not_use_fallback(self):
        runtimes = make_runtimes()

        client = FakeHttpClient(
            {
                "http://primary:9000/v1/chat/completions": 400,
                "http://fallback:9001/v1/chat/completions": 200,
            }
        )

        result = await route_non_stream_request(
            client,
            runtimes,
            {"messages": []},
            FakeStats(),
        )

        self.assertEqual(result.response.status_code, 400)
        self.assertEqual(result.provider_name, "primary")
        self.assertEqual(len(client.calls), 1)

    async def test_all_open_circuits_skip_upstream(self):
        runtimes = make_runtimes()

        await runtimes[0].circuit_breaker.record_failure()
        await runtimes[0].circuit_breaker.record_failure()
        await runtimes[0].circuit_breaker.record_failure()

        await runtimes[1].circuit_breaker.record_failure()
        await runtimes[1].circuit_breaker.record_failure()
        await runtimes[1].circuit_breaker.record_failure()

        client = FakeHttpClient({})
        stats = FakeStats()

        result = await route_non_stream_request(
            client,
            runtimes,
            {"messages": []},
            stats,
        )

        self.assertIsNone(result.response)
        self.assertEqual(result.error, "circuit_open")
        self.assertEqual(client.calls, [])
        self.assertEqual(
            stats.values.get("circuit_open_rejections"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
