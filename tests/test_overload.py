import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as app_module
from test_proxy import FakeAsyncClient


class RejectingGate:
    async def try_acquire(self):
        return False

    async def release(self):
        pass


class OverloadTests(unittest.TestCase):
    def test_chat_returns_503_when_proxy_is_overloaded(self):
        fake_client = FakeAsyncClient(mode="healthy")

        with patch.object(
            app_module.httpx,
            "AsyncClient",
            return_value=fake_client,
        ):
            with TestClient(app_module.app) as client:
                app_module.app.state.concurrency_gate = RejectingGate()

                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "mock-model",
                        "messages": [
                            {
                                "role": "user",
                                "content": "Overload test",
                            }
                        ],
                    },
                )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Proxy overloaded"},
        )


if __name__ == "__main__":
    unittest.main()
