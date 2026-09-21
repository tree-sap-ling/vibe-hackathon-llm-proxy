import unittest

from fastapi.testclient import TestClient

import app.main as app_module


class ProcessPublicMaskTests(unittest.TestCase):
    def test_published_mask_and_exact_demask(self):
        original = (
            "Клиент Иванов Иван Иванович, "
            "паспорт 4509 123456"
        )
        expected_mask = (
            "Клиент И. И. И., "
            "паспорт 45** ****56"
        )

        with TestClient(app_module.app) as client:
            first = client.post(
                "/process",
                json={
                    "payload": original,
                    "payload_id": "public-e2e-1",
                },
            )

            self.assertEqual(
                first.status_code,
                200,
            )

            masked = first.json()["result"]

            self.assertEqual(
                masked,
                expected_mask,
            )
            self.assertNotIn(
                "<PII:",
                masked,
            )

            second = client.post(
                "/process",
                json={
                    "payload": masked,
                    "payload_id": "public-e2e-1",
                },
            )

        self.assertEqual(
            second.status_code,
            200,
        )
        self.assertEqual(
            second.json()["result"],
            original,
        )

    def test_original_retry_returns_same_public_mask(
        self,
    ):
        original = "Email: user@example.com"

        with TestClient(app_module.app) as client:
            first = client.post(
                "/process",
                json={
                    "payload": original,
                    "payload_id": "public-e2e-2",
                },
            )

            retry = client.post(
                "/process",
                json={
                    "payload": original,
                    "payload_id": "public-e2e-2",
                },
            )

        self.assertEqual(
            first.status_code,
            200,
        )
        self.assertEqual(
            retry.status_code,
            200,
        )
        self.assertEqual(
            first.json()["result"],
            "Email: ****@*******.***",
        )
        self.assertEqual(
            retry.json()["result"],
            first.json()["result"],
        )
        self.assertNotIn(
            "<PII:",
            first.json()["result"],
        )

    def test_demask_retry_returns_original_again(self):
        original = (
            "Телефон: +7 (999) 123-45-67."
        )

        with TestClient(app_module.app) as client:
            first = client.post(
                "/process",
                json={
                    "payload": original,
                    "payload_id": "public-e2e-3",
                },
            )

            masked = first.json()["result"]

            second = client.post(
                "/process",
                json={
                    "payload": masked,
                    "payload_id": "public-e2e-3",
                },
            )

            third = client.post(
                "/process",
                json={
                    "payload": masked,
                    "payload_id": "public-e2e-3",
                },
            )

        self.assertEqual(
            first.status_code,
            200,
        )
        self.assertEqual(
            second.status_code,
            200,
        )
        self.assertEqual(
            third.status_code,
            200,
        )
        self.assertEqual(
            second.json()["result"],
            original,
        )
        self.assertEqual(
            third.json()["result"],
            original,
        )

    def test_conflicting_payload_still_returns_409(self):
        first_original = "Email: first@example.com"
        conflicting = "Email: other@example.com"

        with TestClient(app_module.app) as client:
            first = client.post(
                "/process",
                json={
                    "payload": first_original,
                    "payload_id": "public-e2e-4",
                },
            )

            conflict = client.post(
                "/process",
                json={
                    "payload": conflicting,
                    "payload_id": "public-e2e-4",
                },
            )

        self.assertEqual(
            first.status_code,
            200,
        )
        self.assertEqual(
            conflict.status_code,
            409,
        )

    def test_no_pii_payload_stays_unchanged(self):
        original = (
            "Обычный технический текст без ПД."
        )

        with TestClient(app_module.app) as client:
            first = client.post(
                "/process",
                json={
                    "payload": original,
                    "payload_id": "public-e2e-5",
                },
            )

            retry = client.post(
                "/process",
                json={
                    "payload": original,
                    "payload_id": "public-e2e-5",
                },
            )

        self.assertEqual(
            first.status_code,
            200,
        )
        self.assertEqual(
            retry.status_code,
            200,
        )
        self.assertEqual(
            first.json()["result"],
            original,
        )
        self.assertEqual(
            retry.json()["result"],
            original,
        )


if __name__ == "__main__":
    unittest.main()
