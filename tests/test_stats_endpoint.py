import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as app_module
from test_proxy import FakeAsyncClient


class StatsEndpointTests(unittest.TestCase):
    def test_stats_include_each_provider_circuit(self):
        fake_client = FakeAsyncClient(mode="healthy")

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
                    runtimes = (
                        app_module.app.state.provider_runtimes
                    )

                    client.portal.call(
                        runtimes[0].circuit_breaker.record_failure
                    )

                    response = client.get("/stats")

        self.assertEqual(response.status_code, 200)

        providers = response.json()["providers"]

        self.assertEqual(
            providers["primary"]["circuit"]["failure_count"],
            1,
        )
        self.assertEqual(
            providers["fallback"]["circuit"]["failure_count"],
            0,
        )
        self.assertEqual(
            providers["primary"]["circuit"]["state"],
            "closed",
        )
        self.assertEqual(
            providers["fallback"]["circuit"]["state"],
            "closed",
        )

    def test_stats_start_with_zero_counters(self):
        fake_client = FakeAsyncClient(mode="healthy")

        with patch.object(
            app_module.httpx,
            "AsyncClient",
            return_value=fake_client,
        ):
            with TestClient(app_module.app) as client:
                response = client.get("/stats")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["in_flight"], 0)
        self.assertEqual(data["max_in_flight"], 2)
        self.assertEqual(data["total_requests"], 0)
        self.assertEqual(data["completed_requests"], 0)
        self.assertEqual(data["overload_rejections"], 0)
        self.assertEqual(data["circuit_open_rejections"], 0)
        self.assertEqual(data["upstream_errors"], 0)
        self.assertEqual(data["upstream_timeouts"], 0)

        self.assertEqual(data["circuit"]["state"], "closed")
        self.assertEqual(data["circuit"]["failure_count"], 0)
        self.assertEqual(data["circuit"]["failure_threshold"], 3)


if __name__ == "__main__":
    unittest.main()
