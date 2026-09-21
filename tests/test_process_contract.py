import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as app_module


class LifespanOnlyHttpClient:
    async def aclose(self):
        pass


class ProcessContractTests(unittest.TestCase):
    def make_client(self):
        return patch.object(
            app_module.httpx,
            "AsyncClient",
            return_value=LifespanOnlyHttpClient(),
        )

    def test_mask_then_demask_contract(self):
        original = (
            "Клиент Иванов Иван Иванович, "
            "паспорт 4509 123456"
        )

        with self.make_client():
            with TestClient(app_module.app) as client:
                mask_response = client.post(
                    "/process",
                    json={
                        "payload": original,
                        "payload_id": "pair-1",
                    },
                )

                self.assertEqual(
                    mask_response.status_code,
                    200,
                )
                self.assertEqual(
                    set(mask_response.json()),
                    {"result"},
                )

                masked = mask_response.json()["result"]

                self.assertNotEqual(masked, original)
                self.assertNotIn(
                    "Иванов Иван Иванович",
                    masked,
                )
                self.assertNotIn(
                    "4509 123456",
                    masked,
                )

                demask_response = client.post(
                    "/process",
                    json={
                        "payload": masked,
                        "payload_id": "pair-1",
                    },
                )

        self.assertEqual(
            demask_response.status_code,
            200,
        )
        self.assertEqual(
            demask_response.json(),
            {"result": original},
        )

    def test_mask_retry_returns_exact_same_result(self):
        original = "Email: retry@example.com"

        with self.make_client():
            with TestClient(app_module.app) as client:
                first = client.post(
                    "/process",
                    json={
                        "payload": original,
                        "payload_id": "retry-mask",
                    },
                )
                second = client.post(
                    "/process",
                    json={
                        "payload": original,
                        "payload_id": "retry-mask",
                    },
                )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            second.json(),
            first.json(),
        )

    def test_demask_retry_returns_original_again(self):
        original = (
            "Телефон: +7 999 123-45-67."
        )

        with self.make_client():
            with TestClient(app_module.app) as client:
                masked = client.post(
                    "/process",
                    json={
                        "payload": original,
                        "payload_id": "retry-demask",
                    },
                ).json()["result"]

                first = client.post(
                    "/process",
                    json={
                        "payload": masked,
                        "payload_id": "retry-demask",
                    },
                )
                second = client.post(
                    "/process",
                    json={
                        "payload": masked,
                        "payload_id": "retry-demask",
                    },
                )

        self.assertEqual(
            first.json(),
            {"result": original},
        )
        self.assertEqual(
            second.json(),
            {"result": original},
        )

    def test_conflicting_payload_id_returns_409(self):
        with self.make_client():
            with TestClient(app_module.app) as client:
                first = client.post(
                    "/process",
                    json={
                        "payload": (
                            "Email: owner@example.com"
                        ),
                        "payload_id": "conflict-1",
                    },
                )

                conflict = client.post(
                    "/process",
                    json={
                        "payload": (
                            "Email: other@example.com"
                        ),
                        "payload_id": "conflict-1",
                    },
                )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            conflict.status_code,
            409,
        )

    def test_missing_required_fields_return_422(self):
        with self.make_client():
            with TestClient(app_module.app) as client:
                missing_id = client.post(
                    "/process",
                    json={"payload": "text"},
                )
                missing_payload = client.post(
                    "/process",
                    json={"payload_id": "id-1"},
                )

        self.assertEqual(
            missing_id.status_code,
            422,
        )
        self.assertEqual(
            missing_payload.status_code,
            422,
        )

    def test_blank_payload_id_returns_400(self):
        with self.make_client():
            with TestClient(app_module.app) as client:
                response = client.post(
                    "/process",
                    json={
                        "payload": "text",
                        "payload_id": "   ",
                    },
                )

        self.assertEqual(
            response.status_code,
            400,
        )

    def test_payload_without_pii_round_trips(self):
        original = "Обычный текст без данных."

        with self.make_client():
            with TestClient(app_module.app) as client:
                first = client.post(
                    "/process",
                    json={
                        "payload": original,
                        "payload_id": "no-pii",
                    },
                )
                second = client.post(
                    "/process",
                    json={
                        "payload": (
                            first.json()["result"]
                        ),
                        "payload_id": "no-pii",
                    },
                )

        self.assertEqual(
            first.json(),
            {"result": original},
        )
        self.assertEqual(
            second.json(),
            {"result": original},
        )

    def test_pii_metrics_count_only_new_mask(self):
        original = "Email: metrics@example.com"

        with self.make_client():
            with TestClient(app_module.app) as client:
                first = client.post(
                    "/process",
                    json={
                        "payload": original,
                        "payload_id": "metrics-1",
                    },
                )
                masked = first.json()["result"]

                retry = client.post(
                    "/process",
                    json={
                        "payload": original,
                        "payload_id": "metrics-1",
                    },
                )
                demask = client.post(
                    "/process",
                    json={
                        "payload": masked,
                        "payload_id": "metrics-1",
                    },
                )

                stats = client.get("/stats").json()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(demask.status_code, 200)

        self.assertEqual(
            stats["pii"]["processed_requests"],
            1,
        )
        self.assertEqual(
            stats["pii"]["requests_with_pii"],
            1,
        )
        self.assertEqual(
            stats["pii"]["detected_entities"],
            1,
        )
        self.assertEqual(
            stats["pii"]["requests_by_type"],
            {"email": 1},
        )


    def test_new_mask_emits_one_safe_audit_event(self):
        original = "Email: audit.secret@example.com"

        with patch.object(
            app_module,
            "log_pii_audit_event",
        ) as log_mock:
            with self.make_client():
                with TestClient(
                    app_module.app
                ) as client:
                    first = client.post(
                        "/process",
                        json={
                            "payload": original,
                            "payload_id": "audit-1",
                        },
                    )

                    masked = first.json()["result"]

                    retry = client.post(
                        "/process",
                        json={
                            "payload": original,
                            "payload_id": "audit-1",
                        },
                    )

                    demask = client.post(
                        "/process",
                        json={
                            "payload": masked,
                            "payload_id": "audit-1",
                        },
                    )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(demask.status_code, 200)

        self.assertEqual(
            log_mock.call_count,
            1,
        )

        event = log_mock.call_args.args[1]
        event_dict = event.as_dict()

        self.assertEqual(
            event_dict["detected_types"],
            ["email"],
        )
        self.assertEqual(
            event_dict["entity_count"],
            1,
        )

        serialized = repr(event_dict)

        self.assertNotIn(
            "audit.secret@example.com",
            serialized,
        )
        self.assertNotIn(
            masked,
            serialized,
        )
        self.assertNotIn(
            "audit-1",
            serialized,
        )


if __name__ == "__main__":
    unittest.main()
