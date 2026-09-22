import json
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import app.main as app_module


class FakeAsyncClient:
    def __init__(self, mode="healthy"):
        self.mode = mode
        self.posts = []

    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)

        if self.mode == "unavailable":
            raise httpx.ConnectError(
                "upstream unavailable",
                request=request,
            )

        return httpx.Response(
            200,
            json={"status": "ok"},
            request=request,
        )

    async def post(self, url, json, **kwargs):
        self.posts.append(json)
        request = httpx.Request("POST", url)

        if self.mode == "unavailable":
            raise httpx.ConnectError(
                "upstream unavailable",
                request=request,
            )

        if self.mode == "timeout":
            raise httpx.ReadTimeout(
                "upstream timed out",
                request=request,
            )

        messages = json.get("messages", [])
        last_user_message = ""

        for message in reversed(messages):
            if message.get("role") == "user":
                last_user_message = str(
                    message.get("content", "")
                )
                break

        return httpx.Response(
            200,
            json={
                "id": "fake-completion",
                "object": "chat.completion",
                "model": json.get("model", "mock-model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": (
                                f"Mock reply: {last_user_message}"
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
            request=request,
        )

    async def aclose(self):
        pass


class ProxyTests(unittest.TestCase):
    def make_client(self, mode="healthy"):
        fake_client = FakeAsyncClient(mode=mode)
        self.fake_client = fake_client

        patcher = patch.object(
            app_module.httpx,
            "AsyncClient",
            return_value=fake_client,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        client = TestClient(app_module.app)
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)

        return client

    def test_healthz_when_upstream_is_unavailable(self):
        client = self.make_client(mode="unavailable")

        response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readyz_when_upstream_is_healthy(self):
        client = self.make_client(mode="healthy")

        response = client.get("/readyz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_readyz_when_upstream_is_unavailable(self):
        client = self.make_client(mode="unavailable")

        response = client.get("/readyz")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "not_ready"},
        )

    def test_chat_success(self):
        client = self.make_client(mode="healthy")

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "mock-model",
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello test",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["choices"][0]["message"]["content"],
            "Mock reply: Hello test",
        )

    def test_chat_masks_pii_before_upstream_and_demasks_response(self):
        client = self.make_client(mode="healthy")
        original_email = "secret.person@example.com"

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "mock-model",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Email клиента: "
                            + original_email
                        ),
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)

        upstream_payload = self.fake_client.posts[-1]
        serialized = json.dumps(
            upstream_payload,
            ensure_ascii=False,
        )

        self.assertNotIn(
            original_email,
            serialized,
        )
        self.assertIn(
            "<PII:email:",
            upstream_payload["messages"][0]["content"],
        )

        client_content = (
            response.json()["choices"][0]["message"]["content"]
        )

        self.assertIn(
            original_email,
            client_content,
        )
        self.assertNotIn(
            "<PII:",
            client_content,
        )

    def test_chat_stream_with_pii_fails_closed_before_upstream(self):
        client = self.make_client(mode="healthy")
        original_email = "stream.secret@example.com"

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "mock-model",
                "stream": True,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Email клиента: "
                            + original_email
                        ),
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Streaming with detected PII is disabled",
            response.json()["detail"],
        )
        self.assertEqual(
            self.fake_client.posts,
            [],
        )

    def test_chat_returns_502_when_upstream_is_unavailable(self):
        client = self.make_client(mode="unavailable")

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "mock-model",
                "messages": [],
            },
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {"detail": "Upstream provider is unavailable"},
        )

    def test_chat_returns_504_when_upstream_times_out(self):
        client = self.make_client(mode="timeout")

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "mock-model",
                "messages": [],
            },
        )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(
            response.json(),
            {"detail": "Upstream provider timed out"},
        )


if __name__ == "__main__":
    unittest.main()
