import unittest

from app.pii import (
    ConsumerPolicy,
    PiiProcessor,
    PiiType,
    PolicyRegistry,
    build_pii_audit_event,
    log_pii_audit_event,
)


class FakeLogger:
    def __init__(self):
        self.message = None
        self.extra = None

    def info(
        self,
        message: str,
        *,
        extra: dict[str, object],
    ) -> None:
        self.message = message
        self.extra = extra


class PiiObservabilityTests(unittest.TestCase):
    def build_prepared(self):
        policy = ConsumerPolicy(
            system_id="crm",
            enabled_types=frozenset(
                {
                    PiiType.EMAIL,
                    PiiType.PHONE,
                }
            ),
            demask_enabled=True,
        )
        processor = PiiProcessor(
            PolicyRegistry((policy,))
        )

        return processor.prepare_request(
            "crm",
            (
                "Email secret.person@example.com, "
                "телефон +7 999 123-45-67."
            ),
        )

    def test_processing_latency_is_recorded(self):
        prepared = self.build_prepared()

        self.assertGreaterEqual(
            prepared.processing_ms,
            0.0,
        )

    def test_audit_event_contains_types_not_values(self):
        prepared = self.build_prepared()

        event = build_pii_audit_event(
            "req-123",
            prepared,
        )
        fields = event.as_dict()
        serialized = repr(fields)

        self.assertEqual(
            fields["detected_types"],
            ["email", "phone"],
        )
        self.assertEqual(
            fields["entity_count"],
            2,
        )
        self.assertNotIn(
            "secret.person@example.com",
            serialized,
        )
        self.assertNotIn(
            "+7 999 123-45-67",
            serialized,
        )
        self.assertNotIn(
            prepared.masked_text,
            serialized,
        )

    def test_log_helper_never_logs_source_values(self):
        prepared = self.build_prepared()
        event = build_pii_audit_event(
            "req-456",
            prepared,
        )
        logger = FakeLogger()

        log_pii_audit_event(
            logger,
            event,
        )

        logged = repr(logger.extra)

        self.assertEqual(
            logger.message,
            "pii_processing_completed",
        )
        self.assertNotIn(
            "secret.person@example.com",
            logged,
        )
        self.assertNotIn(
            "+7 999 123-45-67",
            logged,
        )
        self.assertIn("'email'", logged)
        self.assertIn("'phone'", logged)

    def test_empty_request_id_is_rejected(self):
        prepared = self.build_prepared()

        with self.assertRaises(ValueError):
            build_pii_audit_event(
                "   ",
                prepared,
            )


if __name__ == "__main__":
    unittest.main()
