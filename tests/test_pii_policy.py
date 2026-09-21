import unittest

from app.pii import (
    ConsumerDisabledError,
    ConsumerPolicy,
    PiiType,
    PolicyRegistry,
    UnknownConsumerError,
    build_default_registry,
)


class PiiPolicyTests(unittest.TestCase):
    def test_authorized_consumer_returns_policy(self):
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
        registry = PolicyRegistry((policy,))

        self.assertEqual(
            registry.get_authorized("crm"),
            policy,
        )

    def test_unknown_consumer_is_rejected(self):
        registry = PolicyRegistry()

        with self.assertRaises(
            UnknownConsumerError
        ):
            registry.get_authorized("unknown")

    def test_disabled_consumer_is_rejected(self):
        registry = PolicyRegistry(
            (
                ConsumerPolicy(
                    system_id="legacy",
                    enabled_types=frozenset(
                        {PiiType.EMAIL}
                    ),
                    enabled=False,
                ),
            )
        )

        with self.assertRaises(
            ConsumerDisabledError
        ):
            registry.get_authorized("legacy")

    def test_duplicate_system_id_is_rejected(self):
        policy = ConsumerPolicy(
            system_id="crm",
            enabled_types=frozenset(
                {PiiType.EMAIL}
            ),
        )

        with self.assertRaises(ValueError):
            PolicyRegistry((policy, policy))

    def test_empty_system_id_is_rejected(self):
        with self.assertRaises(ValueError):
            ConsumerPolicy(
                system_id="",
                enabled_types=frozenset(
                    {PiiType.EMAIL}
                ),
            )

    def test_surrounding_whitespace_is_rejected(self):
        with self.assertRaises(ValueError):
            ConsumerPolicy(
                system_id=" crm ",
                enabled_types=frozenset(
                    {PiiType.EMAIL}
                ),
            )

    def test_policy_can_disable_demasking(self):
        policy = ConsumerPolicy(
            system_id="analytics",
            enabled_types=frozenset(
                {PiiType.EMAIL}
            ),
            demask_enabled=False,
        )

        self.assertFalse(policy.demask_enabled)

    def test_policy_types_filter_detector_registry(self):
        text = (
            "Email user@example.com, "
            "телефон +7 999 123-45-67."
        )
        policy = ConsumerPolicy(
            system_id="email-only",
            enabled_types=frozenset(
                {PiiType.EMAIL}
            ),
        )

        entities = build_default_registry().detect(
            text,
            enabled_types=set(
                policy.enabled_types
            ),
        )

        self.assertEqual(
            [entity.pii_type for entity in entities],
            [PiiType.EMAIL],
        )


if __name__ == "__main__":
    unittest.main()
