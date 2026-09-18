import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import app.main as app_module


class ReadinessAsyncClient:
    def __init__(self):
        self.get_calls = []

    async def get(self, url, **kwargs):
        self.get_calls.append(url)

        request = httpx.Request("GET", url)

        if url.startswith("http://primary:9000"):
            raise httpx.ConnectError(
                "primary unavailable",
                request=request,
            )

        if url.startswith("http://fallback:9001"):
            return httpx.Response(
                200,
                json={"status": "ok"},
                request=request,
            )

        raise AssertionError(f"Unexpected URL: {url}")

    async def aclose(self):
        pass


class FallbackReadinessTests(unittest.TestCase):
    def test_ready_when_fallback_is_healthy(self):
        fake_client = ReadinessAsyncClient()

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
                    response = client.get("/readyz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ready"},
        )

        self.assertEqual(
            fake_client.get_calls,
            [
                "http://primary:9000/healthz",
                "http://fallback:9001/healthz",
            ],
        )


if __name__ == "__main__":
    unittest.main()
