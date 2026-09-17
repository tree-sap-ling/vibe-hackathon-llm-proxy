import unittest

from fastapi.testclient import TestClient

from mock_provider.main import app


class MockProviderTests(unittest.TestCase):
    def test_non_stream_response(self):
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "mock-model",
                    "messages": [
                        {
                            "role": "user",
                            "content": "hello",
                        }
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["choices"][0]["message"]["content"],
            "Mock reply: hello",
        )

    def test_stream_response_uses_sse_and_done_marker(self):
        with TestClient(app) as client:
            with client.stream(
                "POST",
                "/v1/chat/completions",
                json={
                    "model": "mock-model",
                    "stream": True,
                    "mock_delay_ms": 0,
                    "mock_chunk_delay_ms": 0,
                    "messages": [
                        {
                            "role": "user",
                            "content": "hello streaming",
                        }
                    ],
                },
            ) as response:
                body = "".join(response.iter_text())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers["content-type"].startswith(
                "text/event-stream"
            )
        )
        self.assertIn(
            '"object": "chat.completion.chunk"',
            body,
        )
        self.assertIn(
            '"content": "hello "',
            body,
        )
        self.assertIn(
            '"content": "streaming"',
            body,
        )
        self.assertIn("data: [DONE]", body)


if __name__ == "__main__":
    unittest.main()
