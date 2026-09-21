import re
import unittest

from app.pii.models import PiiType
from app.pii.policy import ConsumerPolicy, PolicyRegistry
from app.pii.processor import PiiProcessor


_TOKEN_PATTERN = re.compile(
    r"<PII:[a-z_]+:\d+:[0-9a-f]+>"
)


class PiiRequestIsolationTests(unittest.TestCase):
    def build_processor(self) -> PiiProcessor:
        policy = ConsumerPolicy(
            system_id="crm",
            enabled_types=frozenset(PiiType),
            demask_enabled=True,
            enabled=True,
        )

        return PiiProcessor(
            PolicyRegistry((policy,))
        )

    def test_requests_use_distinct_token_namespaces(self):
        processor = self.build_processor()

        first = processor.prepare_request(
            "crm",
            "Email: first.person@example.com",
        )
        second = processor.prepare_request(
            "crm",
            "Email: second.person@example.com",
        )

        first_tokens = _TOKEN_PATTERN.findall(
            first.masked_text
        )
        second_tokens = _TOKEN_PATTERN.findall(
            second.masked_text
        )

        self.assertEqual(len(first_tokens), 1)
        self.assertEqual(len(second_tokens), 1)
        self.assertNotEqual(
            first_tokens[0],
            second_tokens[0],
        )

    def test_vault_does_not_demask_foreign_request_token(self):
        processor = self.build_processor()

        first = processor.prepare_request(
            "crm",
            "Email: first.person@example.com",
        )
        second = processor.prepare_request(
            "crm",
            "Email: second.person@example.com",
        )

        first_token = _TOKEN_PATTERN.findall(
            first.masked_text
        )[0]
        second_token = _TOKEN_PATTERN.findall(
            second.masked_text
        )[0]

        first_with_foreign = (
            first.masked_text
            + " foreign="
            + second_token
        )
        second_with_foreign = (
            second.masked_text
            + " foreign="
            + first_token
        )

        first_final = processor.finalize_response(
            first,
            first_with_foreign,
        )
        second_final = processor.finalize_response(
            second,
            second_with_foreign,
        )

        self.assertIn(
            "first.person@example.com",
            first_final,
        )
        self.assertNotIn(
            "second.person@example.com",
            first_final,
        )
        self.assertIn(
            second_token,
            first_final,
        )

        self.assertIn(
            "second.person@example.com",
            second_final,
        )
        self.assertNotIn(
            "first.person@example.com",
            second_final,
        )
        self.assertIn(
            first_token,
            second_final,
        )

    def test_each_request_round_trips_only_its_own_values(self):
        processor = self.build_processor()

        first_text = (
            "Email: alpha@example.com; "
            "телефон: +7 999 111-22-33."
        )
        second_text = (
            "Email: beta@example.com; "
            "телефон: +7 999 444-55-66."
        )

        first = processor.prepare_request(
            "crm",
            first_text,
        )
        second = processor.prepare_request(
            "crm",
            second_text,
        )

        self.assertEqual(
            processor.finalize_response(
                first,
                first.masked_text,
            ),
            first_text,
        )
        self.assertEqual(
            processor.finalize_response(
                second,
                second.masked_text,
            ),
            second_text,
        )

        cross_first = processor.finalize_response(
            first,
            second.masked_text,
        )
        cross_second = processor.finalize_response(
            second,
            first.masked_text,
        )

        self.assertNotIn(
            "alpha@example.com",
            cross_first,
        )
        self.assertNotIn(
            "beta@example.com",
            cross_first,
        )
        self.assertNotIn(
            "alpha@example.com",
            cross_second,
        )
        self.assertNotIn(
            "beta@example.com",
            cross_second,
        )


if __name__ == "__main__":
    unittest.main()
