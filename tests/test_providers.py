import os
import unittest
from unittest.mock import patch

from app.providers import get_provider_configs


class ProviderConfigTests(unittest.TestCase):
    def test_default_primary_provider(self):
        with patch.dict(os.environ, {}, clear=True):
            providers = get_provider_configs()

        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0].name, "primary")
        self.assertEqual(
            providers[0].base_url,
            "http://127.0.0.1:9000",
        )
        self.assertIsNone(providers[0].api_key)

    def test_primary_and_fallback_providers(self):
        env = {
            "UPSTREAM_BASE_URL": "http://primary:9000/",
            "UPSTREAM_API_KEY": "primary-test-key",
            "FALLBACK_UPSTREAM_BASE_URL": (
                "http://fallback:9001/"
            ),
            "FALLBACK_UPSTREAM_API_KEY": (
                "fallback-test-key"
            ),
        }

        with patch.dict(os.environ, env, clear=True):
            providers = get_provider_configs()

        self.assertEqual(len(providers), 2)

        self.assertEqual(providers[0].name, "primary")
        self.assertEqual(
            providers[0].base_url,
            "http://primary:9000",
        )
        self.assertEqual(
            providers[0].api_key,
            "primary-test-key",
        )

        self.assertEqual(providers[1].name, "fallback")
        self.assertEqual(
            providers[1].base_url,
            "http://fallback:9001",
        )
        self.assertEqual(
            providers[1].api_key,
            "fallback-test-key",
        )

    def test_duplicate_fallback_is_ignored(self):
        env = {
            "UPSTREAM_BASE_URL": "http://provider:9000",
            "FALLBACK_UPSTREAM_BASE_URL": (
                "http://provider:9000/"
            ),
        }

        with patch.dict(os.environ, env, clear=True):
            providers = get_provider_configs()

        self.assertEqual(len(providers), 1)


if __name__ == "__main__":
    unittest.main()
