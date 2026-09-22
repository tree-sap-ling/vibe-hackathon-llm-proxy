import json
import os
import unittest
from unittest.mock import patch

from app.pii.config import (
    default_consumer_policies,
    get_consumer_policies,
    parse_consumer_policies_json,
)
from app.pii.models import PiiType
from app.pii.processor import PiiProcessor
from app.pii.policy import PolicyRegistry


class PiiConfigTests(unittest.TestCase):
    def test_defaults_preserve_autocheck_and_llm_proxy(self):
        policies = default_consumer_policies()

        self.assertEqual(
            [policy.system_id for policy in policies],
            ["autocheck", "llm-proxy"],
        )

        for policy in policies:
            self.assertEqual(
                policy.enabled_types,
                frozenset(PiiType),
            )
            self.assertTrue(policy.demask_enabled)
            self.assertTrue(policy.enabled)

    def test_missing_env_uses_defaults(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            policies = get_consumer_policies()

        self.assertEqual(
            [policy.system_id for policy in policies],
            ["autocheck", "llm-proxy"],
        )

    def test_custom_policy_parses_enabled_types_and_flags(self):
        raw = json.dumps(
            [
                {
                    "system_id": "crm",
                    "enabled_types": ["email", "phone"],
                    "demask_enabled": False,
                    "enabled": True,
                },
                {
                    "system_id": "analytics",
                    "enabled_types": ["*"],
                    "enabled": False,
                },
            ]
        )

        policies = parse_consumer_policies_json(raw)

        self.assertEqual(len(policies), 2)
        self.assertEqual(
            policies[0].enabled_types,
            frozenset(
                {
                    PiiType.EMAIL,
                    PiiType.PHONE,
                }
            ),
        )
        self.assertFalse(policies[0].demask_enabled)
        self.assertTrue(policies[0].enabled)

        self.assertEqual(
            policies[1].enabled_types,
            frozenset(PiiType),
        )
        self.assertTrue(policies[1].demask_enabled)
        self.assertFalse(policies[1].enabled)

    def test_custom_env_drives_processor_without_code_change(self):
        raw = json.dumps(
            [
                {
                    "system_id": "crm",
                    "enabled_types": ["email"],
                    "demask_enabled": False,
                    "enabled": True,
                }
            ]
        )

        with patch.dict(
            os.environ,
            {"PII_POLICIES_JSON": raw},
            clear=True,
        ):
            policies = get_consumer_policies()

        processor = PiiProcessor(
            PolicyRegistry(policies)
        )
        prepared = processor.prepare_request(
            "crm",
            (
                "Email user@example.com, "
                "телефон +7 999 123-45-67."
            ),
        )

        self.assertIn("<PII:email:", prepared.masked_text)
        self.assertNotIn("user@example.com", prepared.masked_text)
        self.assertIn(
            "+7 999 123-45-67",
            prepared.masked_text,
        )
        self.assertFalse(prepared.demask_enabled)

    def test_unknown_pii_type_is_rejected(self):
        raw = json.dumps(
            [
                {
                    "system_id": "crm",
                    "enabled_types": ["email", "not-a-type"],
                }
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "unknown PII type",
        ):
            parse_consumer_policies_json(raw)

    def test_unknown_field_is_rejected(self):
        raw = json.dumps(
            [
                {
                    "system_id": "crm",
                    "enabled_types": ["email"],
                    "demaks_enabled": True,
                }
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "unknown fields",
        ):
            parse_consumer_policies_json(raw)

    def test_duplicate_system_id_is_rejected(self):
        raw = json.dumps(
            [
                {
                    "system_id": "crm",
                    "enabled_types": ["email"],
                },
                {
                    "system_id": "crm",
                    "enabled_types": ["phone"],
                },
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "duplicate system_id",
        ):
            parse_consumer_policies_json(raw)

    def test_non_boolean_flags_are_rejected(self):
        raw = json.dumps(
            [
                {
                    "system_id": "crm",
                    "enabled_types": ["email"],
                    "enabled": "yes",
                }
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be a JSON boolean",
        ):
            parse_consumer_policies_json(raw)

    def test_invalid_json_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must be valid JSON",
        ):
            parse_consumer_policies_json("{broken")


if __name__ == "__main__":
    unittest.main()
