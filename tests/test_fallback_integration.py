import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import app.main as app_module


class FallbackAsyncClient:
    def __init__(self):
        self.post_calls = []

    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)

        return httpx.Response(
            200,
            json={"status": "ok"},
            request=request,
        )

    async def post(self, url, json, **kwargs):
        self.post_calls.append(url)

        request = httpx.Request("POST", url)

        if url.startswith("http://primary:9000"):
            raise httpx.ConnectError(
                "primary unavailable",
                request=request,
            )

        if url.startswith("http://fallback:9001"):
            return httpx.Response(
                200,
                json={
                    "id": "fallback-response",
                    "object": "chat.completion",
                    "model": "mock-model",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Fallback reply",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
                request=request,
            )

        raise AssertionError(f"Unexpected URL: {url}")

    async def aclose(self):
        pass


class FallbackIntegrationTests(unittest.TestCase):
    def test_primary_failure_falls_back_to_second_provider(self):
        fake_client = FallbackAsyncClient()

        env = {
            "UPSTREAM_BASE_URL": "http://primary:9000",
            "FALLBACK_UPSTREAM_BASE_URL": "http://fallback:9001",
        }

        with patch.dict(os.environ, env, clear=False):
            with patch.object(
                app_module.httpx,
                "AsyncClient",
                return_value=fake_client,
            ):
                with TestClient(app_module.app) as client:
                    response = client.post(
                        "/v1/chat/completions",
                        json={
                            "model": "mock-model",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "fallback test",
                                }
                            ],
                        },
                    )

                    stats = client.portal.call(
                        app_module.app.state.stats.snapshot
                    )

                    runtimes = (
                        app_module.app.state.provider_runtimes
                    )

                    primary_circuit = client.portal.call(
                        runtimes[0].circuit_breaker.snapshot
                    )
                    fallback_circuit = client.portal.call(
                        runtimes[1].circuit_breaker.snapshot
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["choices"][0]["message"]["content"],
            "Fallback reply",
        )

        self.assertEqual(
            fake_client.post_calls,
            [
                "http://primary:9000/v1/chat/completions",
                "http://fallback:9001/v1/chat/completions",
            ],
        )

        self.assertEqual(stats["upstream_errors"], 1)
        self.assertEqual(stats["completed_requests"], 1)

        self.assertEqual(
            primary_circuit["failure_count"],
            1,
        )
        self.assertEqual(
            fallback_circuit["state"],
            "closed",
        )


if __name__ == "__main__":
    unittest.main()
