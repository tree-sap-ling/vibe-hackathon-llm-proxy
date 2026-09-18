import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import app.main as app_module


class FailingStreamingAsyncClient:
    def __init__(self):
        self.send_calls = 0

    def build_request(self, method, url, **kwargs):
        return httpx.Request(
            method,
            url,
            json=kwargs.get("json"),
        )

    async def send(self, request, **kwargs):
        self.send_calls += 1

        raise httpx.ConnectError(
            "streaming upstream unavailable",
            request=request,
        )

    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)

        return httpx.Response(
            200,
            json={"status": "ok"},
            request=request,
        )

    async def aclose(self):
        pass


class StreamingCircuitIntegrationTests(unittest.TestCase):
    def test_streaming_failures_open_circuit(self):
        fake_client = FailingStreamingAsyncClient()

        with patch.object(
            app_module.httpx,
            "AsyncClient",
            return_value=fake_client,
        ):
            with TestClient(app_module.app) as client:
                payload = {
                    "model": "mock-model",
                    "stream": True,
                    "messages": [
                        {
                            "role": "user",
                            "content": "stream circuit test",
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

                breaker_snapshot = client.portal.call(
                    app_module.app.state.circuit_breaker.snapshot
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

        self.assertEqual(fake_client.send_calls, 3)

        self.assertEqual(
            breaker_snapshot["state"],
            "open",
        )
        self.assertEqual(
            breaker_snapshot["failure_count"],
            3,
        )

        self.assertEqual(
            stats_snapshot["circuit_open_rejections"],
            1,
        )
        self.assertEqual(
            stats_snapshot["upstream_errors"],
            3,
        )


if __name__ == "__main__":
    unittest.main()
