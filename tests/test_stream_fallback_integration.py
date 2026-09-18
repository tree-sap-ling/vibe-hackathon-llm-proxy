import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import app.main as app_module


class FakeSSEStream(httpx.AsyncByteStream):
    def __init__(self):
        self.closed = False

    async def __aiter__(self):
        yield b'data: {"message":"fallback first"}\n\n'
        yield b'data: [DONE]\n\n'

    async def aclose(self):
        self.closed = True


class FailingAfterFirstChunkStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'data: {"message":"primary first"}\n\n'

        raise httpx.ReadError(
            "primary stream failed after first chunk",
            request=httpx.Request(
                "POST",
                "http://primary:9000/v1/chat/completions",
            ),
        )

    async def aclose(self):
        pass


class PostFirstChunkFailureAsyncClient:
    def __init__(self):
        self.send_calls = []

    def build_request(self, method, url, **kwargs):
        return httpx.Request(
            method,
            url,
            json=kwargs.get("json"),
            headers=kwargs.get("headers"),
        )

    async def send(self, request, **kwargs):
        url = str(request.url)
        self.send_calls.append(url)

        if url.startswith("http://primary:9000"):
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/event-stream",
                },
                stream=FailingAfterFirstChunkStream(),
                request=request,
            )

        if url.startswith("http://fallback:9001"):
            raise AssertionError(
                "Fallback must not be used after first chunk"
            )

        raise AssertionError(f"Unexpected URL: {url}")

    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)

        return httpx.Response(
            200,
            json={"status": "ok"},
            request=request,
        )

    async def aclose(self):
        pass


class FailingBeforeFirstChunkStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        raise httpx.ReadError(
            "primary stream failed before first chunk",
            request=httpx.Request(
                "POST",
                "http://primary:9000/v1/chat/completions",
            ),
        )
        yield b""

    async def aclose(self):
        pass


class FirstChunkFailureAsyncClient:
    def __init__(self):
        self.send_calls = []
        self.fallback_stream = FakeSSEStream()

    def build_request(self, method, url, **kwargs):
        return httpx.Request(
            method,
            url,
            json=kwargs.get("json"),
            headers=kwargs.get("headers"),
        )

    async def send(self, request, **kwargs):
        url = str(request.url)
        self.send_calls.append(url)

        if url.startswith("http://primary:9000"):
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/event-stream",
                },
                stream=FailingBeforeFirstChunkStream(),
                request=request,
            )

        if url.startswith("http://fallback:9001"):
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/event-stream",
                },
                stream=self.fallback_stream,
                request=request,
            )

        raise AssertionError(f"Unexpected URL: {url}")

    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)

        return httpx.Response(
            200,
            json={"status": "ok"},
            request=request,
        )

    async def aclose(self):
        pass


class FallbackStreamingAsyncClient:
    def __init__(self):
        self.send_calls = []
        self.fallback_stream = FakeSSEStream()

    def build_request(self, method, url, **kwargs):
        return httpx.Request(
            method,
            url,
            json=kwargs.get("json"),
            headers=kwargs.get("headers"),
        )

    async def send(self, request, **kwargs):
        url = str(request.url)
        self.send_calls.append(url)

        if url.startswith("http://primary:9000"):
            raise httpx.ConnectError(
                "primary unavailable",
                request=request,
            )

        if url.startswith("http://fallback:9001"):
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/event-stream",
                },
                stream=self.fallback_stream,
                request=request,
            )

        raise AssertionError(f"Unexpected URL: {url}")

    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)

        return httpx.Response(
            200,
            json={"status": "ok"},
            request=request,
        )

    async def aclose(self):
        pass


class StreamFallbackIntegrationTests(unittest.TestCase):
    def test_failure_after_first_chunk_does_not_use_fallback(self):
        fake_client = PostFirstChunkFailureAsyncClient()

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
                            "stream": True,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "no fallback after chunk",
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

        self.assertIn(
            'data: {"message":"primary first"}',
            response.text,
        )

        self.assertNotIn(
            "fallback",
            response.text,
        )

        self.assertEqual(
            fake_client.send_calls,
            [
                "http://primary:9000/v1/chat/completions",
            ],
        )

        self.assertEqual(
            stats["upstream_errors"],
            1,
        )

        self.assertEqual(
            stats["completed_requests"],
            0,
        )

        self.assertEqual(
            primary_circuit["failure_count"],
            1,
        )

        self.assertEqual(
            fallback_circuit["failure_count"],
            0,
        )


    def test_primary_read_failure_before_first_chunk_uses_fallback(self):
        fake_client = FirstChunkFailureAsyncClient()

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
                            "stream": True,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "first chunk fallback",
                                }
                            ],
                        },
                    )

                    stats = client.portal.call(
                        app_module.app.state.stats.snapshot
                    )

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            'data: {"message":"fallback first"}',
            response.text,
        )
        self.assertIn(
            "data: [DONE]",
            response.text,
        )

        self.assertEqual(
            fake_client.send_calls,
            [
                "http://primary:9000/v1/chat/completions",
                "http://fallback:9001/v1/chat/completions",
            ],
        )

        self.assertEqual(
            stats["upstream_errors"],
            1,
        )


    def test_primary_connect_failure_falls_back_before_stream_starts(self):
        fake_client = FallbackStreamingAsyncClient()

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
                            "stream": True,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "stream fallback test",
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

        self.assertIn(
            'data: {"message":"fallback first"}',
            response.text,
        )
        self.assertIn(
            "data: [DONE]",
            response.text,
        )

        self.assertEqual(
            fake_client.send_calls,
            [
                "http://primary:9000/v1/chat/completions",
                "http://fallback:9001/v1/chat/completions",
            ],
        )

        self.assertTrue(fake_client.fallback_stream.closed)

        self.assertEqual(
            stats["upstream_errors"],
            1,
        )
        self.assertEqual(
            stats["completed_requests"],
            1,
        )

        self.assertEqual(
            primary_circuit["failure_count"],
            1,
        )
        self.assertEqual(
            fallback_circuit["state"],
            "closed",
        )
        self.assertEqual(
            fallback_circuit["failure_count"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
