import unittest

from app.pii import ConsumerPolicy, PiiProcessor, PiiType, PolicyRegistry
from app.pii.chat import finalize_chat_response, prepare_chat_payload


class PiiChatTests(unittest.TestCase):
    def build_processor(self):
        return PiiProcessor(
            PolicyRegistry(
                (
                    ConsumerPolicy(
                        system_id="llm-proxy",
                        enabled_types=frozenset(PiiType),
                        demask_enabled=True,
                        enabled=True,
                    ),
                )
            )
        )

    def test_prepare_masks_string_content_and_restores_response(self):
        processor = self.build_processor()
        original = "Email клиента: user@example.com"

        prepared_chat = prepare_chat_payload(
            {
                "model": "mock-model",
                "messages": [
                    {
                        "role": "user",
                        "content": original,
                    }
                ],
            },
            processor,
            "llm-proxy",
        )

        masked = prepared_chat.payload["messages"][0]["content"]

        self.assertTrue(prepared_chat.contains_pii)
        self.assertNotIn("user@example.com", masked)
        self.assertIn("<PII:email:", masked)

        response = finalize_chat_response(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Echo: " + masked,
                        }
                    }
                ]
            },
            processor,
            prepared_chat.prepared_requests,
        )

        content = response["choices"][0]["message"]["content"]

        self.assertIn("user@example.com", content)
        self.assertNotIn("<PII:", content)

    def test_prepare_masks_openai_text_parts(self):
        processor = self.build_processor()

        prepared_chat = prepare_chat_payload(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Телефон клиента: "
                                    "+7 (912) 345-67-89"
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "https://example.invalid/image.png"
                                },
                            },
                        ],
                    }
                ]
            },
            processor,
            "llm-proxy",
        )

        parts = prepared_chat.payload["messages"][0]["content"]

        self.assertTrue(prepared_chat.contains_pii)
        self.assertNotIn(
            "+7 (912) 345-67-89",
            parts[0]["text"],
        )
        self.assertIn(
            "<PII:phone:",
            parts[0]["text"],
        )
        self.assertEqual(
            parts[1]["image_url"]["url"],
            "https://example.invalid/image.png",
        )

    def test_no_pii_keeps_payload_semantically_unchanged(self):
        processor = self.build_processor()
        payload = {
            "model": "mock-model",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello test",
                }
            ],
        }

        prepared_chat = prepare_chat_payload(
            payload,
            processor,
            "llm-proxy",
        )

        self.assertFalse(prepared_chat.contains_pii)
        self.assertEqual(prepared_chat.payload, payload)


if __name__ == "__main__":
    unittest.main()
