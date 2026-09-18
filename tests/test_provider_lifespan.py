import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as app_module
from tests.test_proxy import FakeAsyncClient


class ProviderLifespanTests(unittest.TestCase):
    def test_lifespan_builds_primary_and_fallback_runtimes(self):
        env = {
            "UPSTREAM_BASE_URL": "http://primary:9000",
            "FALLBACK_UPSTREAM_BASE_URL": "http://fallback:9001",
            "CIRCUIT_FAILURE_THRESHOLD": "3",
            "CIRCUIT_RECOVERY_TIMEOUT_SECONDS": "5",
        }

        fake_client = FakeAsyncClient(mode="healthy")

        with patch.dict(os.environ, env, clear=False):
            with patch.object(
                app_module.httpx,
                "AsyncClient",
                return_value=fake_client,
            ):
                with TestClient(app_module.app):
                    runtimes = (
                        app_module.app.state.provider_runtimes
                    )

                    self.assertEqual(len(runtimes), 2)

                    self.assertEqual(
                        runtimes[0].config.name,
                        "primary",
                    )
                    self.assertEqual(
                        runtimes[0].config.base_url,
                        "http://primary:9000",
                    )

                    self.assertEqual(
                        runtimes[1].config.name,
                        "fallback",
                    )
                    self.assertEqual(
                        runtimes[1].config.base_url,
                        "http://fallback:9001",
                    )

                    self.assertIsNot(
                        runtimes[0].circuit_breaker,
                        runtimes[1].circuit_breaker,
                    )

                    self.assertIs(
                        app_module.app.state.circuit_breaker,
                        runtimes[0].circuit_breaker,
                    )


if __name__ == "__main__":
    unittest.main()
