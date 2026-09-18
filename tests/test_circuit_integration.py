import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import app.main as app_module


class FailingAsyncClient:
    def __init__(self):
        self.post_calls = 0

    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)

        return httpx.Response(
            200,
            json={"status": "ok"},
            request=request,
        )

    async def post(self, url, json, **kwargs):
        self.post_calls += 1

        request = httpx.Request("POST", url)

        raise httpx.ConnectError(
            "upstream unavailable",
            request=request,
        )

    async def aclose(self):
        pass


class CircuitBreakerIntegrationTests(unittest.TestCase):
    def test_circuit_opens_after_three_upstream_failures(self):
        fake_client = FailingAsyncClient()

        with patch.object(
            app_module.httpx,
            "AsyncClient",
            return_value=fake_client,
        ):
            with TestClient(app_module.app) as client:
                payload = {
                    "model": "mock-model",
                    "messages": [
                        {
                            "role": "user",
                            "content": "circuit test",
                        }
                    ],
                }

                first = client.post(
                    "/v1/chat/completions",
                    json=payload,
                )
                second = client.post(
                    "/v1/chat/completions",
                    json=payload,
                )
                third = client.post(
                    "/v1/chat/completions",
                    json=payload,
                )
                fourth = client.post(
                    "/v1/chat/completions",
                    json=payload,
                )

                breaker = (
                    app_module.app.state.circuit_breaker
                )
                snapshot = client.portal.call(
                    breaker.snapshot
                )
                stats_snapshot = client.portal.call(
                    app_module.app.state.stats.snapshot
                )

        self.assertEqual(first.status_code, 502)
        self.assertEqual(second.status_code, 502)
        self.assertEqual(third.status_code, 502)

        self.assertEqual(fourth.status_code, 503)
        self.assertEqual(
            fourth.json(),
            {"detail": "Upstream circuit is open"},
        )

        self.assertEqual(fake_client.post_calls, 3)
        self.assertEqual(snapshot["state"], "open")
        self.assertEqual(snapshot["failure_count"], 3)
        self.assertEqual(
            stats_snapshot["circuit_open_rejections"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
